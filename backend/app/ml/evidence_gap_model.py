"""Hybrid evidence gap detection system.

Tier 1: rule-based expectations from the evidence taxonomy.
Tier 2: lightweight semantic recovery from free text and witness narratives.
Tier 3: optional ML suggestions from the trained scikit-learn model.

The semantic tier is deliberately CPU-friendly: it uses small TF-IDF similarity
checks over short snippets instead of a heavy local LLM. This makes the system
more flexible on varied charge-sheet formats without materially increasing
runtime or deployment size.
"""

from __future__ import annotations

import logging
import os
import pickle
import re
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from app.ml.evidence_taxonomy import (
    ALL_CATEGORIES,
    EVIDENCE_CATEGORIES,
    classify_evidence_list,
    get_expected_evidence,
)

logger = logging.getLogger(__name__)

_MODEL_DIR = Path(os.getenv("EVIDENCE_MODEL_DIR", "/app/models"))
_MODEL_PATH = _MODEL_DIR / "evidence_gap_model.pkl"
_TFIDF_PATH = _MODEL_DIR / "evidence_tfidf.pkl"

_SEMANTIC_MIN_SCORE = float(os.getenv("EVIDENCE_SEMANTIC_MIN_SCORE", "0.45"))
_SEMANTIC_MAX_SNIPPETS = int(os.getenv("EVIDENCE_SEMANTIC_MAX_SNIPPETS", "30"))

_SEMANTIC_HINTS: Dict[str, List[str]] = {
    "post_mortem_report": ["post mortem report", "autopsy report", "pm report"],
    "scene_of_crime_report": ["scene of crime report", "spot panchnama", "crime scene report"],
    "forensic_report": ["forensic report", "forensic analysis", "lab examination report"],
    "cctv_footage": ["cctv footage", "surveillance footage", "camera recording"],
    "witness_statements_161": ["witness statement", "statement under 161", "examination of witness"],
    "victim_statement_164": ["victim statement under 164", "statement before magistrate", "164 crpc statement"],
    "medical_examination": ["medical examination report", "injury report", "mlc report"],
    "weapon_recovery": ["weapon recovery memo", "knife recovered", "firearm recovery"],
    "electronic_evidence": [
        "electronic evidence",
        "digital evidence",
        "mobile phone extraction",
        "whatsapp chat export",
        "mobile screenshot record",
    ],
    "financial_records": ["bank statement", "transaction record", "financial records"],
    "identification_parade": ["identification parade", "tip report", "test identification"],
    "call_detail_records": ["call detail record", "tower dump", "cdr analysis"],
    "narcotics_test_report": ["chemical analysis report", "narcotics test report", "drug sample report"],
    "property_valuation": ["property valuation", "stolen property valuation", "valuation certificate"],
    "confession_statement": ["confession statement", "disclosure statement", "voluntary statement"],
    "site_plan_map": ["site plan map", "spot map", "sketch map"],
    "dna_report": ["dna report", "dna analysis", "dna profiling report"],
    "fingerprint_report": ["fingerprint report", "latent print analysis", "finger print examination"],
    "seizure_memo": ["seizure memo", "seizure panchnama", "seized article memo"],
    "fsl_report": ["fsl report", "forensic science laboratory report", "fsl opinion"],
}


def _normalise_section(section: str) -> str:
    return re.sub(r"[\(\[].*$", "", section.strip().replace(" ", ""))


def _infer_crime_category(
    charges: List[Dict[str, Any]],
    fir_data: Optional[Dict[str, Any]] = None,
) -> str:
    """Best-effort inference of crime category from charges or FIR NLP."""
    if fir_data:
        nlp_category = fir_data.get("nlp_classification")
        if nlp_category:
            mapping = {
                "murder": "murder",
                "rape_sexoff": "sexual_offences",
                "dacoity_robbery": "robbery",
                "kidnapping": "kidnapping",
                "domestic_violence": "murder",
                "assault": "attempt_to_murder",
                "fraud": "fraud",
                "cybercrime": "cybercrime",
                "narcotics": "narcotics",
                "theft": "property_crime",
                "other": "property_crime",
            }
            return mapping.get(nlp_category, "property_crime")

    try:
        from app.legal_db import get_section

        for charge in charges:
            section = charge.get("section")
            act = (charge.get("act") or "IPC").lower()
            if not section:
                continue
            entry = get_section(_normalise_section(section), act)
            if not entry:
                continue
            category = entry.get("category")
            if not category:
                continue
            mapping = {
                "murder": "murder",
                "attempt_to_murder": "attempt_to_murder",
                "assault": "attempt_to_murder",
                "sexual_offences": "sexual_offences",
                "kidnapping": "kidnapping",
                "robbery": "robbery",
                "dacoity": "dacoity",
                "fraud": "fraud",
                "property_crime": "property_crime",
                "cybercrime": "cybercrime",
                "narcotics": "narcotics",
            }
            return mapping.get(category, category)
    except Exception:
        logger.debug("Section-based crime category inference failed.", exc_info=True)

    return "property_crime"


def _unique_snippets(snippets: List[str], limit: int = _SEMANTIC_MAX_SNIPPETS) -> List[str]:
    seen: Set[str] = set()
    deduped: List[str] = []
    for snippet in snippets:
        cleaned = re.sub(r"\s+", " ", snippet or "").strip()
        if not cleaned or cleaned.lower() in seen:
            continue
        seen.add(cleaned.lower())
        deduped.append(cleaned)
        if len(deduped) >= limit:
            break
    return deduped


def _fallback_similarity(prototypes: List[str], snippets: List[str]) -> tuple[float, str]:
    best_score = 0.0
    best_snippet = ""
    for prototype in prototypes:
        for snippet in snippets:
            score = SequenceMatcher(None, prototype.lower(), snippet.lower()).ratio()
            if score > best_score:
                best_score = score
                best_snippet = snippet
    return best_score, best_snippet


def _semantic_similarity(prototypes: List[str], snippets: List[str]) -> tuple[float, str]:
    """Return best similarity score and supporting snippet."""
    if not prototypes or not snippets:
        return 0.0, ""

    try:
        import numpy as np
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity

        docs = prototypes + snippets
        vectorizer = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), lowercase=True)
        matrix = vectorizer.fit_transform(docs)
        proto_matrix = matrix[: len(prototypes)]
        snippet_matrix = matrix[len(prototypes):]
        similarities = cosine_similarity(proto_matrix, snippet_matrix)
        best_index = np.unravel_index(similarities.argmax(), similarities.shape)
        return float(similarities[best_index]), snippets[int(best_index[1])]
    except Exception:
        logger.debug("TF-IDF semantic similarity fallback engaged.", exc_info=True)
        return _fallback_similarity(prototypes, snippets)


class EvidenceGapDetector:
    """Hybrid evidence gap detection.

    Tier 1: rule-based expectation matching.
    Tier 2: semantic evidence recovery from raw text.
    Tier 3: optional ML suggestion model.
    """

    def __init__(self):
        self._model = None
        self._tfidf = None
        self._try_load_model()

    def _try_load_model(self) -> None:
        try:
            if _MODEL_PATH.exists() and _TFIDF_PATH.exists():
                with open(_MODEL_PATH, "rb") as model_file:
                    self._model = pickle.load(model_file)
                with open(_TFIDF_PATH, "rb") as tfidf_file:
                    self._tfidf = pickle.load(tfidf_file)
                logger.info("Evidence gap ML model loaded from %s", _MODEL_PATH)
            else:
                logger.info("No evidence gap ML model found; ML suggestion tier disabled.")
        except Exception:
            logger.warning("Failed to load evidence gap ML model.", exc_info=True)
            self._model = None
            self._tfidf = None

    @property
    def has_ml_model(self) -> bool:
        return self._model is not None and self._tfidf is not None

    def detect_gaps(
        self,
        chargesheet_data: Dict[str, Any],
        fir_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Run hybrid gap detection and return an evidence report."""
        chargesheet_id = str(chargesheet_data.get("id", ""))
        charges = chargesheet_data.get("charges_json") or []
        evidence = chargesheet_data.get("evidence_json") or []

        crime_category = _infer_crime_category(charges, fir_data)
        charged_sections = [
            _normalise_section(charge.get("section", ""))
            for charge in charges
            if charge.get("section")
        ]

        expected = get_expected_evidence(crime_category, charged_sections)
        expected_categories = {item["category"] for item in expected}

        evidence_present = classify_evidence_list(evidence)
        present_categories: Set[str] = {item["category"] for item in evidence_present}

        semantic_matches: List[Dict[str, Any]] = []
        try:
            semantic_matches = self._run_semantic_presence_tier(
                crime_category=crime_category,
                expected=expected,
                chargesheet_data=chargesheet_data,
                present_categories=present_categories,
            )
        except Exception:
            logger.warning("Semantic evidence tier failed.", exc_info=True)
            semantic_matches = []

        for match in semantic_matches:
            if match["category"] not in present_categories:
                present_categories.add(match["category"])
                evidence_present.append(match)

        tier1_gaps: List[Dict[str, Any]] = []
        for expected_item in expected:
            category = expected_item["category"]
            if category in present_categories:
                continue
            tier1_gaps.append(
                {
                    "category": category,
                    "tier": "rule_based",
                    "severity": "critical" if expected_item["weight"] == "critical" else "important",
                    "recommendation": self._make_recommendation(
                        category,
                        crime_category,
                        expected_item["weight"],
                    ),
                    "legal_basis": self._get_legal_basis(category),
                    "confidence": 1.0,
                }
            )

        tier1_gap_categories = {gap["category"] for gap in tier1_gaps}

        tier3_gaps: List[Dict[str, Any]] = []
        if self.has_ml_model:
            try:
                tier3_gaps = self._run_ml_tier(
                    crime_category=crime_category,
                    charged_sections=charged_sections,
                    chargesheet_data=chargesheet_data,
                    present_categories=present_categories,
                    tier1_gap_categories=tier1_gap_categories,
                )
            except Exception:
                logger.warning("ML suggestion tier failed; using rules + semantics only.", exc_info=True)

        all_gaps = tier1_gaps + tier3_gaps
        total_expected = len(expected_categories)
        total_present = len(present_categories & expected_categories)

        tiers_run = ["rule_based", "semantic_recovery"]
        if self.has_ml_model:
            tiers_run.append("ml_pattern")

        return {
            "chargesheet_id": chargesheet_id,
            "crime_category": crime_category,
            "charged_sections": charged_sections,
            "evidence_present": evidence_present,
            "evidence_gaps": all_gaps,
            "evidence_coverage_pct": round(
                (total_present / total_expected * 100) if total_expected > 0 else 100.0,
                1,
            ),
            "total_expected": total_expected,
            "total_present": total_present,
            "total_gaps": len(all_gaps),
            "analysis_metadata": {
                "semantic_matches_used": len(semantic_matches),
                "semantic_threshold": _SEMANTIC_MIN_SCORE,
                "ml_enabled": self.has_ml_model,
                "tiers_run": tiers_run,
            },
        }

    def _collect_semantic_snippets(self, chargesheet_data: Dict[str, Any]) -> List[str]:
        snippets: List[str] = []

        for item in chargesheet_data.get("evidence_json") or []:
            text = " ".join(
                part
                for part in [
                    item.get("description", ""),
                    item.get("type", ""),
                    item.get("status", ""),
                ]
                if part
            ).strip()
            if text:
                snippets.append(text)

        for witness in chargesheet_data.get("witnesses_json") or []:
            text = " ".join(
                part
                for part in [
                    witness.get("name", ""),
                    witness.get("role", ""),
                    witness.get("statement_summary", ""),
                ]
                if part
            ).strip()
            if text:
                snippets.append(text)

        raw_text = chargesheet_data.get("raw_text", "") or ""
        for line in raw_text.splitlines():
            cleaned = re.sub(r"\s+", " ", line).strip(" -:\t")
            if not cleaned or len(cleaned) < 8 or len(cleaned) > 180:
                continue
            if re.search(
                r"\b(report|statement|memo|footage|record|map|analysis|certificate|medical|cctv|bank|fsl|dna|fingerprint|seizure|recovery|whatsapp|chat|mobile|screenshot|device|email|upi)\b",
                cleaned,
                re.IGNORECASE,
            ):
                snippets.append(cleaned)

        return _unique_snippets(snippets)

    def _run_semantic_presence_tier(
        self,
        crime_category: str,
        expected: List[Dict[str, Any]],
        chargesheet_data: Dict[str, Any],
        present_categories: Set[str],
    ) -> List[Dict[str, Any]]:
        """Recover likely evidence already present but missed by strict extraction."""
        snippets = self._collect_semantic_snippets(chargesheet_data)
        if not snippets:
            return []

        matches: List[Dict[str, Any]] = []
        for expected_item in expected:
            category = expected_item["category"]
            if category in present_categories:
                continue

            prototypes = _SEMANTIC_HINTS.get(category) or [
                EVIDENCE_CATEGORIES.get(category, {}).get("description", category.replace("_", " "))
            ]
            score, snippet = _semantic_similarity(prototypes, snippets)
            if score < _SEMANTIC_MIN_SCORE:
                continue

            matches.append(
                {
                    "category": category,
                    "source_text": snippet,
                    "confidence": round(score, 2),
                    "detected_by": "semantic_match",
                    "crime_category": crime_category,
                }
            )

        return matches

    def _run_ml_tier(
        self,
        crime_category: str,
        charged_sections: List[str],
        chargesheet_data: Dict[str, Any],
        present_categories: Set[str],
        tier1_gap_categories: Set[str],
    ) -> List[Dict[str, Any]]:
        """Run the optional ML model for non-blocking suggestions."""
        raw_text = chargesheet_data.get("raw_text", "")
        text_features = f"{crime_category} {' '.join(charged_sections)} {raw_text[:500]}"
        matrix = self._tfidf.transform([text_features])

        probabilities: List[float] = []
        for estimator in self._model.estimators_:
            prediction = estimator.predict_proba(matrix)[0]
            probabilities.append(prediction[1] if len(prediction) == 2 else prediction[0])

        gaps: List[Dict[str, Any]] = []
        for index, category in enumerate(ALL_CATEGORIES):
            if index >= len(probabilities):
                break
            probability = probabilities[index]
            if probability >= 0.3:
                continue
            if category in present_categories or category in tier1_gap_categories:
                continue

            category_info = EVIDENCE_CATEGORIES.get(category, {})
            applies_to = category_info.get("applies_to", [])
            if "all" not in applies_to and crime_category not in applies_to:
                continue

            gaps.append(
                {
                    "category": category,
                    "tier": "ml_pattern",
                    "severity": "suggested",
                    "recommendation": (
                        f"{category_info.get('description', category.replace('_', ' ').title())} "
                        f"is commonly present in similar cases and may strengthen the case file."
                    ),
                    "legal_basis": self._get_legal_basis(category),
                    "confidence": round(1.0 - probability, 2),
                }
            )

        return gaps

    def _make_recommendation(self, category: str, crime: str, weight: str) -> str:
        description = EVIDENCE_CATEGORIES.get(category, {}).get(
            "description",
            category.replace("_", " "),
        )
        if weight == "critical":
            return (
                f"{description} is mandatory or strongly expected for "
                f"{crime.replace('_', ' ')} cases. Obtain or justify its absence before filing."
            )
        return (
            f"{description} is commonly expected in {crime.replace('_', ' ')} cases. "
            f"Consider obtaining it to strengthen the prosecution record."
        )

    def _get_legal_basis(self, category: str) -> str:
        legal_basis = {
            "post_mortem_report": "Section 174 CrPC / Section 194 BNSS (inquest)",
            "scene_of_crime_report": "Section 173 CrPC / Section 193 BNSS",
            "forensic_report": "Section 293 CrPC / expert evidence",
            "witness_statements_161": "Section 161 CrPC / Section 180 BNSS",
            "victim_statement_164": "Section 164 CrPC / Section 183 BNSS",
            "medical_examination": "Section 53 CrPC / Section 184 BNSS",
            "seizure_memo": "Section 102 CrPC / seizure procedure",
            "narcotics_test_report": "Section 36A NDPS Act",
            "electronic_evidence": "Section 65B Evidence Act / Section 63 BSA",
            "identification_parade": "Section 9 Evidence Act",
        }
        return legal_basis.get(category, "Section 173 CrPC / Section 193 BNSS")

    def train(self, training_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Train the optional scikit-learn suggestion model."""
        import numpy as np
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.linear_model import LogisticRegression
        from sklearn.metrics import classification_report
        from sklearn.model_selection import train_test_split
        from sklearn.multioutput import MultiOutputClassifier

        texts = [item.get("text_features", "") for item in training_data]
        labels = np.array([[item.get(category, 0) for category in ALL_CATEGORIES] for item in training_data])

        self._tfidf = TfidfVectorizer(max_features=3000, ngram_range=(1, 2))
        matrix = self._tfidf.fit_transform(texts)

        x_train, x_test, y_train, y_test = train_test_split(
            matrix,
            labels,
            test_size=0.2,
            random_state=42,
        )

        base_model = LogisticRegression(max_iter=500, C=1.0, solver="lbfgs")
        self._model = MultiOutputClassifier(base_model)
        self._model.fit(x_train, y_train)

        predicted = self._model.predict(x_test)
        report = classification_report(
            y_test,
            predicted,
            target_names=ALL_CATEGORIES,
            output_dict=True,
            zero_division=0,
        )

        metrics = {
            "macro_f1": report.get("macro avg", {}).get("f1-score", 0.0),
            "micro_f1": report.get("micro avg", {}).get("f1-score", 0.0),
            "accuracy": report.get("accuracy", 0.0) if "accuracy" in report else 0.0,
            "per_category": {
                category: {
                    "precision": report.get(category, {}).get("precision", 0.0),
                    "recall": report.get(category, {}).get("recall", 0.0),
                    "f1": report.get(category, {}).get("f1-score", 0.0),
                }
                for category in ALL_CATEGORIES
                if category in report
            },
        }

        logger.info("Evidence gap model trained. macro-F1=%.3f", metrics["macro_f1"])
        return metrics

    def save_model(self, path: Optional[str] = None) -> None:
        model_path = Path(path) if path else _MODEL_PATH
        tfidf_path = model_path.parent / "evidence_tfidf.pkl"
        model_path.parent.mkdir(parents=True, exist_ok=True)

        with open(model_path, "wb") as model_file:
            pickle.dump(self._model, model_file)
        with open(tfidf_path, "wb") as tfidf_file:
            pickle.dump(self._tfidf, tfidf_file)
        logger.info("Evidence gap model saved to %s", model_path)

    def load_model(self, path: Optional[str] = None) -> None:
        model_path = Path(path) if path else _MODEL_PATH
        tfidf_path = model_path.parent / "evidence_tfidf.pkl"

        with open(model_path, "rb") as model_file:
            self._model = pickle.load(model_file)
        with open(tfidf_path, "rb") as tfidf_file:
            self._tfidf = pickle.load(tfidf_file)
        logger.info("Evidence gap model loaded from %s", model_path)
