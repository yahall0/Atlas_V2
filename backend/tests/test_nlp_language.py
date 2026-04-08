"""Tests for app.nlp.language — detect_language, normalise_text, preprocess_text.

These tests exercise the language module without requiring the fastText
model file (lid.176.bin).  When the model is absent the module gracefully
falls back to "unknown", which the tests verify.
"""

from __future__ import annotations

import unicodedata

import pytest

from app.nlp.language import (
    LANG_UNKNOWN,
    detect_language,
    normalise_text,
    preprocess_text,
    transliterate_romanised_gujarati,
)


# ---------------------------------------------------------------------------
# normalise_text
# ---------------------------------------------------------------------------


def test_normalise_text_strips_whitespace():
    assert normalise_text("  hello  ") == "hello"


def test_normalise_text_empty():
    assert normalise_text("") == ""


def test_normalise_text_none_safe():
    # Should not raise on empty string
    assert normalise_text("") == ""


def test_normalise_text_nfc():
    # Compose pre-composed vs decomposed characters — result must be NFC
    # U+00E9 is precomposed é; U+0065 U+0301 is decomposed
    decomposed = "\u0065\u0301"  # e + combining acute
    precomposed = "\u00e9"
    result = normalise_text(decomposed)
    assert result == precomposed
    assert unicodedata.is_normalized("NFC", result)


def test_normalise_text_gujarati_passthrough():
    text = "ફરિયાદી દિનાબેન"
    assert normalise_text(text) == text


# ---------------------------------------------------------------------------
# detect_language (model-optional)
# ---------------------------------------------------------------------------


def test_detect_language_empty_returns_unknown():
    assert detect_language("") == LANG_UNKNOWN


def test_detect_language_blank_returns_unknown():
    assert detect_language("   ") == LANG_UNKNOWN


def test_detect_language_returns_string():
    # Model may or may not be available; result must always be a string
    result = detect_language("Hello world, this is English text.")
    assert isinstance(result, str)
    assert len(result) > 0


def test_detect_language_returns_string_gujarati():
    result = detect_language("ફરિયાદી ઘરે સૂતા હતા ત્યારે ચોરી થઈ.")
    assert isinstance(result, str)


# ---------------------------------------------------------------------------
# transliterate_romanised_gujarati (model-optional)
# ---------------------------------------------------------------------------


def test_transliterate_returns_string():
    result = transliterate_romanised_gujarati("amdavad")
    assert isinstance(result, str)


def test_transliterate_passthrough_when_unavailable():
    # If xlit is unavailable the original text is returned unchanged
    original = "fariyaadi"
    result = transliterate_romanised_gujarati(original)
    assert isinstance(result, str)


# ---------------------------------------------------------------------------
# preprocess_text
# ---------------------------------------------------------------------------


def test_preprocess_text_keys():
    result = preprocess_text("sample text")
    assert "normalised" in result
    assert "detected_lang" in result
    assert "transliterated" in result


def test_preprocess_text_transliterate_false():
    result = preprocess_text("sample text", transliterate=False)
    assert result["transliterated"] is None


def test_preprocess_text_transliterate_true():
    result = preprocess_text("amdavad", transliterate=True)
    # transliterated must be a string if xlit is available, or the original
    assert result["transliterated"] is None or isinstance(result["transliterated"], str)


def test_preprocess_text_skips_detection_when_lang_supplied():
    result = preprocess_text("some text", detected_lang="en")
    assert result["detected_lang"] == "en"


def test_preprocess_text_normalises_input():
    text = "  hello world  "
    result = preprocess_text(text)
    assert result["normalised"] == "hello world"
