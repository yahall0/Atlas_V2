"""Tests for app.nlp.classify — ATLASClassifier and classify_fir.

Uses keyword-heuristic mode (no model file required).
"""

from __future__ import annotations

import pytest

from app.nlp.classify import (
    ATLAS_CATEGORIES,
    ATLASClassifier,
    ATLASPrediction,
    classify_fir,
)


# ---------------------------------------------------------------------------
# ATLAS_CATEGORIES constant
# ---------------------------------------------------------------------------


def test_atlas_categories_non_empty():
    assert len(ATLAS_CATEGORIES) >= 10


def test_atlas_categories_has_other():
    assert "other" in ATLAS_CATEGORIES


# ---------------------------------------------------------------------------
# ATLASPrediction dataclass
# ---------------------------------------------------------------------------


def test_atlasprediction_fields():
    p = ATLASPrediction(category="theft", confidence=0.75, method="heuristic")
    assert p.category == "theft"
    assert p.confidence == 0.75
    assert p.method == "heuristic"
    assert p.raw_scores is None


# ---------------------------------------------------------------------------
# ATLASClassifier — heuristic mode
# ---------------------------------------------------------------------------


@pytest.fixture
def classifier():
    return ATLASClassifier(checkpoint="")


def test_classifier_returns_prediction(classifier):
    result = classifier.classify("The accused committed theft and robbery.")
    assert isinstance(result, ATLASPrediction)
    assert result.category in ATLAS_CATEGORIES


def test_classifier_empty_text(classifier):
    result = classifier.classify("")
    assert result.category == "other"
    assert result.confidence == 0.0
    assert result.method == "default"


def test_classifier_blank_text(classifier):
    result = classifier.classify("   ")
    assert result.category == "other"


def test_classifier_theft_keywords(classifier):
    text = "Gold ornaments and cash were stolen during the night. Section 379 applied."
    result = classifier.classify(text)
    assert result.category == "theft"
    assert result.confidence > 0.4


def test_classifier_murder_keywords(classifier):
    text = "The accused murdered the victim. Section 302 IPC applied."
    result = classifier.classify(text)
    assert result.category == "murder"


def test_classifier_fraud_keywords(classifier):
    text = "The accused deceived and cheated the complainant. Section 420."
    result = classifier.classify(text)
    assert result.category == "fraud"


def test_classifier_confidence_range(classifier):
    result = classifier.classify("assault and battery with weapon 324.")
    assert 0.0 <= result.confidence <= 1.0


def test_classifier_method_heuristic(classifier):
    result = classifier.classify("some crime text with narcotics drug.")
    assert result.method == "heuristic"


# ---------------------------------------------------------------------------
# classify_fir module-level function
# ---------------------------------------------------------------------------


def test_classify_fir_returns_prediction():
    result = classify_fir("theft of property from house", log_to_mlflow=False)
    assert isinstance(result, ATLASPrediction)


def test_classify_fir_mlflow_disabled():
    # log_to_mlflow=False must not raise even when MLflow is unavailable
    try:
        classify_fir("some text", log_to_mlflow=False)
    except Exception as exc:
        pytest.fail(f"classify_fir raised unexpectedly: {exc}")


def test_classify_fir_gujarati_text():
    # Gujarati theft FIR excerpt
    text = "ફરિયાદી ઘરે ચોરી થઈ, સોનાના ઘરેણાં ચોરાઈ ગયા."
    result = classify_fir(text, log_to_mlflow=False)
    assert isinstance(result, ATLASPrediction)
    assert result.category in ATLAS_CATEGORIES
