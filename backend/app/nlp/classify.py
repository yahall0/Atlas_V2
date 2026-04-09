"""FIR category classification.

Fallback chain (best → fastest):
  1. Fine-tuned MuRIL checkpoint (INDIC_BERT_CHECKPOINT), if confidence ≥ threshold
  2. Zero-shot NLI (MoritzLaurer/mDeBERTa-v3-base-mnli-xnli) — no training data needed
  3. Keyword heuristics — deterministic, always available

For most FIRs, section_map.py (called in ingest.py) already provides the
classification from registered sections.  This module handles FIRs where
no sections are available or the section lookup returns None.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import mlflow  # type: ignore

from app.nlp.zero_shot import zero_shot_classify  # type: ignore

logger = logging.getLogger(__name__)

_CHECKPOINT = os.getenv("INDIC_BERT_CHECKPOINT", "")
_INDIC_BERT_MODEL = os.getenv("INDIC_BERT_MODEL", "google/muril-base-cased")
_CACHE_DIR = os.getenv("TRANSFORMERS_CACHE", "/transformers_cache")

# Minimum softmax confidence for a model prediction to be accepted.
# 1/11 classes ≈ 0.091 is random chance; anything below 0.25 is treated as
# near-random and falls back to keyword heuristics.
_MODEL_CONFIDENCE_THRESHOLD = float(os.getenv("NLP_CONFIDENCE_THRESHOLD", "0.25"))
_MLFLOW_TRACKING_URI = os.getenv("MLFLOW_TRACKING_URI", "http://mlflow:5000")

# ---------------------------------------------------------------------------
# ATLAS crime categories (BNS Chapter-aligned)
# ---------------------------------------------------------------------------

ATLAS_CATEGORIES: list[str] = [
    "theft",             # BNS Ch.XVII §303-326
    "assault",           # BNS Ch.XVI §115-146
    "fraud",             # BNS Ch.XVII §316-336
    "murder",            # BNS Ch.VI §100-113
    "rape_sexoff",       # BNS Ch.V §63-99
    "cybercrime",        # IT Act §66 family
    "narcotics",         # NDPS Act
    "kidnapping",        # BNS Ch.XIV §137-154
    "dacoity_robbery",   # BNS Ch.XVII §309-314
    "domestic_violence", # PWDVA 2005
    "other",             # catch-all
]

# Simple keyword heuristics used when model checkpoint is unavailable.
# Maps category → list of Gujarati + English keywords (lowercase).
_KEYWORD_HEURISTICS: dict[str, list[str]] = {
    "murder": ["murder", "killed", "death", "302", "homicide", "હત્યા", "ખૂન"],
    "rape_sexoff": ["rape", "376", "sexual", "assault", "pocso", "બળાત્કાર"],
    "theft": ["theft", "stolen", "rob", "steal", "379", "380", "ચોરી"],
    "fraud": ["fraud", "cheat", "deceive", "420", "419", "છેતરપિંડી"],
    "assault": ["assault", "beat", "hit", "hurt", "323", "324", "325", "326", "મારામારી"],
    "cybercrime": ["cyber", "phishing", "hacking", "online", "66c", "66d"],
    "narcotics": ["ndps", "drug", "narcotic", "ganja", "smack", "ડ્રગ"],
    "kidnapping": ["kidnap", "abduct", "365", "366", "363", "અપહરણ"],
    "dacoity_robbery": ["dacoity", "robbery", "dacoit", "394", "395", "396", "ડાકુ"],
    "domestic_violence": ["domestic", "cruelty", "498a", "dowry", "498", "ઘરેલુ"],
}


# ---------------------------------------------------------------------------
# Prediction result
# ---------------------------------------------------------------------------


@dataclass
class ATLASPrediction:
    """Classification result returned by ``ATLASClassifier.classify``."""

    category: str
    confidence: float  # [0.0, 1.0]
    method: str        # "model" | "heuristic" | "default"
    raw_scores: Optional[dict] = None  # per-class softmax scores if model used


# ---------------------------------------------------------------------------
# Classifier
# ---------------------------------------------------------------------------


class ATLASClassifier:
    """IndicBERT-backed FIR classifier.

    Parameters
    ----------
    checkpoint:
        Path or HuggingFace hub ID of a fine-tuned model checkpoint.
        Defaults to the value of the ``INDIC_BERT_CHECKPOINT`` env var.
        If empty, falls back to keyword heuristics.
    """

    def __init__(self, checkpoint: str = _CHECKPOINT) -> None:
        self.checkpoint = checkpoint or ""
        self._model = None
        self._tokenizer = None
        self._id2label: dict[int, str] = {}

        if self.checkpoint:
            self._load_model()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _load_model(self) -> None:
        try:
            from transformers import (  # type: ignore
                AutoModelForSequenceClassification,
                AutoTokenizer,
            )

            self._tokenizer = AutoTokenizer.from_pretrained(
                self.checkpoint, cache_dir=_CACHE_DIR
            )
            self._model = AutoModelForSequenceClassification.from_pretrained(
                self.checkpoint, cache_dir=_CACHE_DIR
            )
            self._model.eval()
            self._id2label = dict(self._model.config.id2label or {})
            # Fall back to label_map.json if config.id2label is empty
            if not self._id2label:
                _label_map_path = Path(self.checkpoint) / "label_map.json"
                if _label_map_path.exists():
                    import json as _json
                    _label_map = _json.loads(_label_map_path.read_text(encoding="utf-8"))
                    self._id2label = {v: k for k, v in _label_map.items()}
                    logger.info("Loaded id2label from label_map.json (%d labels)", len(self._id2label))
            logger.info("ATLASClassifier model loaded from %s", self.checkpoint)
        except Exception as exc:
            logger.warning(
                "Could not load fine-tuned checkpoint '%s' (%s); "
                "falling back to keyword heuristics.",
                self.checkpoint,
                exc,
            )
            self._model = None
            self._tokenizer = None

    def _heuristic_classify(self, text: str) -> ATLASPrediction:
        """Return a prediction based on keyword matching."""
        text_lower = text.lower()
        best_cat = "other"
        best_count = 0
        for cat, keywords in _KEYWORD_HEURISTICS.items():
            count = sum(1 for kw in keywords if kw in text_lower)
            if count > best_count:
                best_count = count
                best_cat = cat
        confidence = min(0.5 + best_count * 0.1, 0.85) if best_count > 0 else 0.3
        return ATLASPrediction(
            category=best_cat,
            confidence=confidence,
            method="heuristic",
        )

    def _model_classify(self, text: str) -> ATLASPrediction:
        """Run inference using the fine-tuned IndicBERT checkpoint."""
        import torch  # type: ignore

        inputs = self._tokenizer(
            text,
            max_length=512,
            truncation=True,
            padding="max_length",
            return_tensors="pt",
        )
        with torch.no_grad():
            logits = self._model(**inputs).logits
            probs = torch.softmax(logits, dim=-1)[0]

        idx = int(probs.argmax())
        label = self._id2label.get(idx, ATLAS_CATEGORIES[idx % len(ATLAS_CATEGORIES)])
        raw_scores = {
            self._id2label.get(i, str(i)): float(probs[i])
            for i in range(len(probs))
        }
        return ATLASPrediction(
            category=label,
            confidence=float(probs[idx]),
            method="model",
            raw_scores=raw_scores,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def classify(self, text: str) -> ATLASPrediction:
        """Classify *text* into one of ``ATLAS_CATEGORIES``.

        Uses the fine-tuned model if available, otherwise falls back to
        keyword heuristics.

        Parameters
        ----------
        text:
            Pre-processed (NFC-normalised) FIR narrative or full text.
        """
        if not text or not text.strip():
            return ATLASPrediction(category="other", confidence=0.0, method="default")

        if self._model is not None and self._tokenizer is not None:
            prediction = self._model_classify(text)
            if prediction.confidence >= _MODEL_CONFIDENCE_THRESHOLD:
                return prediction
            logger.debug(
                "Model confidence %.3f below threshold %.3f; trying zero-shot.",
                prediction.confidence,
                _MODEL_CONFIDENCE_THRESHOLD,
            )

        # Zero-shot NLI fallback — multilingual, no training data required
        zs = zero_shot_classify(text)
        if zs is not None:
            category, score = zs
            return ATLASPrediction(category=category, confidence=score, method="zero_shot")

        return self._heuristic_classify(text)


# ---------------------------------------------------------------------------
# Module-level helper
# ---------------------------------------------------------------------------

_default_classifier: Optional[ATLASClassifier] = None


def classify_fir(text: str, *, log_to_mlflow: bool = False) -> ATLASPrediction:
    """Classify a FIR using the default ``ATLASClassifier`` singleton.

    Parameters
    ----------
    text:
        Pre-processed FIR text.
    log_to_mlflow:
        If ``True``, log the prediction as an MLflow run metric.
    """
    global _default_classifier
    if _default_classifier is None:
        _default_classifier = ATLASClassifier()

    prediction = _default_classifier.classify(text)

    if log_to_mlflow:
        try:
            mlflow.set_tracking_uri(_MLFLOW_TRACKING_URI)
            with mlflow.start_run(run_name="fir_inference", nested=True):
                mlflow.log_metric("confidence", prediction.confidence)
                mlflow.log_param("category", prediction.category)
                mlflow.log_param("method", prediction.method)
        except Exception as exc:
            logger.debug("MLflow logging failed (non-fatal): %s", exc)

    return prediction
