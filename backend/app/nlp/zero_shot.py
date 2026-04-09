"""Zero-shot FIR classification using a multilingual NLI model.

Uses ``MoritzLaurer/mDeBERTa-v3-base-mnli-xnli`` (~270 MB, multilingual) via
the HuggingFace ``zero-shot-classification`` pipeline.  No labelled training
data is required — the model scores each candidate label as a natural-language
hypothesis against the FIR text, so it handles Gujarati, Hindi, and English
without fine-tuning.

The model is downloaded once on first use and cached to TRANSFORMERS_CACHE.
Set ``ZERO_SHOT_MODEL`` env var to override the default model ID.

Fallback hierarchy (in classify.py):
  1. fine-tuned checkpoint (if INDIC_BERT_CHECKPOINT set and confidence ≥ threshold)
  2. zero-shot NLI  ← this module
  3. keyword heuristics (no network/model needed)
"""

from __future__ import annotations

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

_ZERO_SHOT_MODEL = os.getenv(
    "ZERO_SHOT_MODEL",
    "MoritzLaurer/mDeBERTa-v3-base-mnli-xnli",
)
_CACHE_DIR = os.getenv("TRANSFORMERS_CACHE", "/transformers_cache")

# Human-readable hypothesis strings per category.
# Phrased as "this is a case of …" so the NLI model scores entailment correctly.
# Bilingual phrases improve cross-lingual transfer for Gujarati/Hindi FIRs.
_CANDIDATE_LABELS: dict[str, str] = {
    "theft":             "theft, stealing, or robbery of property (ચોરી, લૂંટ)",
    "assault":           "physical assault, attack, or causing bodily harm (મારામારી, ઈજા)",
    "fraud":             "fraud, cheating, financial deception, or forgery (છેતરપિંડી)",
    "murder":            "murder, homicide, or culpable homicide (હત્યા)",
    "rape_sexoff":       "rape, sexual assault, or sexual offence (બળાત્કાર, જાતીય સતામણી)",
    "cybercrime":        "cybercrime, hacking, online fraud, or identity theft",
    "narcotics":         "narcotics, drug trafficking, or illegal substance possession (ડ્રગ)",
    "kidnapping":        "kidnapping, abduction, or wrongful confinement (અપહરણ)",
    "dacoity_robbery":   "dacoity, armed robbery, or gang robbery (ડાકુ, લૂંટ)",
    "domestic_violence": "domestic violence, cruelty to wife, or dowry harassment (ઘરેલુ હિંસા)",
    "other":             "other criminal offence or miscellaneous crime",
}

# Category order for the pipeline — must stay parallel to _CANDIDATE_LABELS keys
_LABEL_KEYS: list[str] = list(_CANDIDATE_LABELS.keys())
_HYPOTHESES: list[str] = list(_CANDIDATE_LABELS.values())

# Minimum entailment score below which zero-shot result is not trusted
_ZERO_SHOT_THRESHOLD = float(os.getenv("ZERO_SHOT_THRESHOLD", "0.20"))

# Max characters fed to the NLI model. Long narratives don't improve accuracy
# and make CPU inference extremely slow (each of 11 labels is a forward pass).
# First ~600 chars capture the FIR header + opening facts — enough for classification.
_MAX_INPUT_CHARS = int(os.getenv("ZERO_SHOT_MAX_CHARS", "600"))

_pipeline = None  # lazy-loaded on first call


def _get_pipeline():
    global _pipeline
    if _pipeline is None:
        try:
            from transformers import pipeline  # type: ignore

            logger.info("Loading zero-shot model %s …", _ZERO_SHOT_MODEL)
            _pipeline = pipeline(
                "zero-shot-classification",
                model=_ZERO_SHOT_MODEL,
                cache_dir=_CACHE_DIR,
                # Use CPU — no GPU expected in this deployment
                device=-1,
            )
            logger.info("Zero-shot model loaded.")
        except Exception as exc:
            logger.warning("Could not load zero-shot model (%s).", exc)
    return _pipeline


def zero_shot_classify(text: str) -> Optional[tuple[str, float]]:
    """Return *(category, confidence)* using zero-shot NLI, or *None* on failure.

    Parameters
    ----------
    text:
        FIR narrative text (any language — model handles multilingual input).

    Returns
    -------
    A *(category_key, score)* tuple where *category_key* is one of
    ``ATLAS_CATEGORIES`` and *score* is the entailment probability [0, 1].
    Returns *None* if the model is unavailable or the top score is below
    ``_ZERO_SHOT_THRESHOLD``.
    """
    pipe = _get_pipeline()
    if pipe is None:
        return None

    # Truncate to avoid extremely slow CPU inference on long narratives
    text = text[:_MAX_INPUT_CHARS]

    try:
        result = pipe(
            text,
            candidate_labels=_HYPOTHESES,
            hypothesis_template="{}",
            multi_label=False,
        )
        # result["labels"] are the hypothesis strings; map back to category keys
        top_hypothesis = result["labels"][0]
        top_score = float(result["scores"][0])

        # Find the matching category key
        try:
            idx = _HYPOTHESES.index(top_hypothesis)
            category = _LABEL_KEYS[idx]
        except ValueError:
            logger.warning("Could not map zero-shot label '%s' back to category.", top_hypothesis)
            return None

        if top_score < _ZERO_SHOT_THRESHOLD:
            logger.debug(
                "Zero-shot score %.3f below threshold %.3f for top label '%s'.",
                top_score, _ZERO_SHOT_THRESHOLD, category,
            )
            return None

        return category, top_score

    except Exception as exc:
        logger.warning("Zero-shot inference failed: %s", exc)
        return None
