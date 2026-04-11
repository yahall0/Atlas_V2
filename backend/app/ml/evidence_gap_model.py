"""Two-tier evidence gap detection system.

Tier 1 — Rule-based: deterministic check using evidence taxonomy.
Tier 2 — ML-based: scikit-learn multi-label classifier for pattern detection.

All inference runs on CPU. Model is <10 MB.
"""

from __future__ import annotations

import logging
import os
import pickle
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from app.ml.evidence_taxonomy import (
    ALL_CATEGORIES,
    ALL_CRIME_TYPES,
    EVIDENCE_CATEGORIES,
    classify_evidence_list,
    get_expected_evidence,
)

logger = logging.getLogger(__name__)

_MODEL_DIR = Path(os.getenv("EVIDENCE_MODEL_DIR", "/app/models"))
_MODEL_PATH = _MODEL_DIR / "evidence_gap_model.pkl"
_TFIDF_PATH = _MODEL_DIR / "evidence_tfidf.pkl"

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


def _normalise_section(s: str) -> str:
    return re.sub(r"[\(\[].*$", "", s.strip().replace(" ", ""))


def _infer_crime_category(
    charges: List[Dict[str, Any]],
    fir_data: Optional[Dict[str, Any]] = None,
) -> str:
    """Best-effort inference of crime category from charges or FIR NLP."""
    if fir_data:
        nlp_cat = fir_data.get("nlp_classification")
        if nlp_cat:
            # Map NLP categories to evidence taxonomy categories
            _MAP = {
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
            return _MAP.get(nlp_cat, "property_crime")

    # Fallback: infer from sections using legal_db
    try:
        from app.legal_db import get_section
        for charge in charges:
            sec = charge.get("section")
            act = (charge.get("act") or "IPC").lower()
            if sec:
                entry = get_section(_normalise_section(sec), act)
                if entry:
                    cat = entry.get("category")
                    if cat:
                        _MAP2 = {
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
                        return _MAP2.get(cat, cat)
    except Exception:
        pass

    return "property_crime"


# ─────────────────────────────────────────────────────────────────────────────
# Evidence Gap Detector
# ─────────────────────────────────────────────────────────────────────────────


class EvidenceGapDetector:
    """Two-tier evidence gap detection.

    Tier 1: rule-based (always runs).
    Tier 2: ML pattern detection (runs if model is loaded).
    """

    def __init__(self):
        self._model = None
        self._tfidf = None
        self._try_load_model()

    def _try_load_model(self) -> None:
        """Attempt to load trained model from disk."""
        try:
            if _MODEL_PATH.exists() and _TFIDF_PATH.exists():
                with open(_MODEL_PATH, "rb") as f:
                    self._model = pickle.load(f)
                with open(_TFIDF_PATH, "rb") as f:
                    self._tfidf = pickle.load(f)
                logger.info("Evidence gap ML model loaded from %s", _MODEL_PATH)
            else:
                logger.info("No evidence gap ML model found; Tier 2 disabled.")
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
        """Run two-tier gap detection and return an EvidenceGapReport.

        Parameters
        ----------
        chargesheet_data : dict
            Charge-sheet row from DB (charges_json, evidence_json, etc.).
        fir_data : dict or None
            Linked FIR data if available.
        """
        cs_id = str(chargesheet_data.get("id", ""))
        charges = chargesheet_data.get("charges_json") or []
        evidence = chargesheet_data.get("evidence_json") or []

        # Determine crime category
        crime_category = _infer_crime_category(charges, fir_data)

        # Extract charged section numbers
        charged_sections = [
            _normalise_section(c.get("section", ""))
            for c in charges if c.get("section")
        ]

        # Classify present evidence
        evidence_present = classify_evidence_list(evidence)
        present_categories: Set[str] = {e["category"] for e in evidence_present}

        # Tier 1: rule-based gap detection
        expected = get_expected_evidence(crime_category, charged_sections)
        expected_categories = {e["category"] for e in expected}
        expected_weights = {e["category"]: e["weight"] for e in expected}

        tier1_gaps: List[Dict[str, Any]] = []
        for exp in expected:
            cat = exp["category"]
            if cat not in present_categories:
                tier1_gaps.append({
                    "category": cat,
                    "tier": "rule_based",
                    "severity": "critical" if exp["weight"] == "critical" else "important",
                    "recommendation": self._make_recommendation(cat, crime_category, exp["weight"]),
                    "legal_basis": self._get_legal_basis(cat),
                    "confidence": 1.0,
                })

        tier1_gap_cats = {g["category"] for g in tier1_gaps}

        # Tier 2: ML pattern detection
        tier2_gaps: List[Dict[str, Any]] = []
        if self.has_ml_model:
            try:
                ml_gaps = self._run_ml_tier(
                    crime_category, charged_sections, chargesheet_data,
                    present_categories, tier1_gap_cats,
                )
                tier2_gaps = ml_gaps
            except Exception:
                logger.warning("ML tier failed; using Tier 1 only.", exc_info=True)

        all_gaps = tier1_gaps + tier2_gaps
        total_expected = len(expected_categories)
        total_present = len(present_categories & expected_categories)

        return {
            "chargesheet_id": cs_id,
            "crime_category": crime_category,
            "charged_sections": charged_sections,
            "evidence_present": evidence_present,
            "evidence_gaps": all_gaps,
            "evidence_coverage_pct": round(
                (total_present / total_expected * 100) if total_expected > 0 else 100.0, 1
            ),
            "total_expected": total_expected,
            "total_present": total_present,
            "total_gaps": len(all_gaps),
        }

    def _run_ml_tier(
        self,
        crime_category: str,
        charged_sections: List[str],
        chargesheet_data: Dict[str, Any],
        present_categories: Set[str],
        tier1_gap_cats: Set[str],
    ) -> List[Dict[str, Any]]:
        """Run the ML model and return additional gaps not found by Tier 1."""
        import numpy as np

        # Build feature text
        raw_text = chargesheet_data.get("raw_text", "")
        text_features = f"{crime_category} {' '.join(charged_sections)} {raw_text[:500]}"

        # Transform
        X = self._tfidf.transform([text_features])

        # Predict probabilities
        probas = []
        for estimator in self._model.estimators_:
            p = estimator.predict_proba(X)[0]
            # predict_proba returns [p_class0, p_class1]; take p(class=1)
            if len(p) == 2:
                probas.append(p[1])
            else:
                probas.append(p[0])

        gaps: List[Dict[str, Any]] = []
        for idx, cat in enumerate(ALL_CATEGORIES):
            if idx >= len(probas):
                break
            prob = probas[idx]
            # Low probability of being present + not already flagged
            if prob < 0.3 and cat not in present_categories and cat not in tier1_gap_cats:
                # Only suggest if the category is at least somewhat relevant
                cat_info = EVIDENCE_CATEGORIES.get(cat, {})
                applies = cat_info.get("applies_to", [])
                if "all" not in applies and crime_category not in applies:
                    continue

                gaps.append({
                    "category": cat,
                    "tier": "ml_pattern",
                    "severity": "suggested",
                    "recommendation": (
                        f"{cat_info.get('description', cat.replace('_', ' ').title())} "
                        f"is frequently present in similar cases and may strengthen "
                        f"the prosecution case."
                    ),
                    "legal_basis": self._get_legal_basis(cat),
                    "confidence": round(1.0 - prob, 2),
                })

        return gaps

    def _make_recommendation(self, category: str, crime: str, weight: str) -> str:
        """Generate a human-readable recommendation for a gap."""
        desc = EVIDENCE_CATEGORIES.get(category, {}).get(
            "description", category.replace("_", " ")
        )
        if weight == "critical":
            return (
                f"{desc} is mandatory for {crime.replace('_', ' ')} cases. "
                f"Request from investigating team before filing."
            )
        return (
            f"{desc} is commonly expected in {crime.replace('_', ' ')} cases. "
            f"Consider obtaining to strengthen the case."
        )

    def _get_legal_basis(self, category: str) -> str:
        """Return legal basis string for an evidence category."""
        _LEGAL_BASIS = {
            "post_mortem_report": "Section 174 CrPC / Section 194 BNSS (Inquest)",
            "scene_of_crime_report": "Section 173(1)(b) CrPC / Section 193 BNSS",
            "forensic_report": "Section 293 CrPC / Expert evidence",
            "witness_statements_161": "Section 161 CrPC / Section 180 BNSS",
            "victim_statement_164": "Section 164 CrPC / Section 183 BNSS",
            "medical_examination": "Section 53 CrPC / Section 184 BNSS",
            "seizure_memo": "Section 102 CrPC / Seizure procedure",
            "narcotics_test_report": "Section 36A NDPS Act",
            "electronic_evidence": "Section 65B Indian Evidence Act / Section 63 BSA",
            "identification_parade": "Section 9 Indian Evidence Act",
        }
        return _LEGAL_BASIS.get(category, "Section 173 CrPC / Section 193 BNSS")

    def train(self, training_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Train the Tier 2 ML model from labelled data.

        Parameters
        ----------
        training_data : list[dict]
            Each dict: ``text_features``, ``crime_category``, and
            one boolean key per evidence category.

        Returns
        -------
        dict
            Training metrics (accuracy, f1, etc.).
        """
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.linear_model import LogisticRegression
        from sklearn.multioutput import MultiOutputClassifier
        from sklearn.model_selection import train_test_split
        from sklearn.metrics import classification_report
        import numpy as np

        # Build features and labels
        texts = [d.get("text_features", "") for d in training_data]
        y = np.array([
            [d.get(cat, 0) for cat in ALL_CATEGORIES]
            for d in training_data
        ])

        # TF-IDF
        self._tfidf = TfidfVectorizer(max_features=3000, ngram_range=(1, 2))
        X = self._tfidf.fit_transform(texts)

        # Split
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42,
        )

        # Train
        base = LogisticRegression(max_iter=500, C=1.0, solver="lbfgs")
        self._model = MultiOutputClassifier(base)
        self._model.fit(X_train, y_train)

        # Evaluate
        y_pred = self._model.predict(X_test)
        report = classification_report(
            y_test, y_pred, target_names=ALL_CATEGORIES,
            output_dict=True, zero_division=0,
        )

        metrics = {
            "macro_f1": report.get("macro avg", {}).get("f1-score", 0.0),
            "micro_f1": report.get("micro avg", {}).get("f1-score", 0.0),
            "accuracy": report.get("accuracy", 0.0) if "accuracy" in report else 0.0,
            "per_category": {
                cat: {
                    "precision": report.get(cat, {}).get("precision", 0.0),
                    "recall": report.get(cat, {}).get("recall", 0.0),
                    "f1": report.get(cat, {}).get("f1-score", 0.0),
                }
                for cat in ALL_CATEGORIES
                if cat in report
            },
        }

        logger.info("Evidence gap model trained. macro-F1=%.3f", metrics["macro_f1"])
        return metrics

    def save_model(self, path: Optional[str] = None) -> None:
        """Save trained model and vectorizer to disk."""
        model_path = Path(path) if path else _MODEL_PATH
        tfidf_path = model_path.parent / "evidence_tfidf.pkl"
        model_path.parent.mkdir(parents=True, exist_ok=True)

        with open(model_path, "wb") as f:
            pickle.dump(self._model, f)
        with open(tfidf_path, "wb") as f:
            pickle.dump(self._tfidf, f)
        logger.info("Model saved to %s", model_path)

    def load_model(self, path: Optional[str] = None) -> None:
        """Load model from disk."""
        model_path = Path(path) if path else _MODEL_PATH
        tfidf_path = model_path.parent / "evidence_tfidf.pkl"

        with open(model_path, "rb") as f:
            self._model = pickle.load(f)
        with open(tfidf_path, "rb") as f:
            self._tfidf = pickle.load(f)
        logger.info("Model loaded from %s", model_path)
