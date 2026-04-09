"""Language detection and Gujarati text normalisation.

Wraps fastText lid.176.bin for script-level detection and IndicXlit for
Romanised-Gujarati → native-script transliteration.  All functions are
pure (stateless) except the module-level model singletons which are
loaded lazily on first use.
"""

from __future__ import annotations

import logging
import os
import unicodedata
from functools import lru_cache
from typing import Optional

logger = logging.getLogger(__name__)

# FastText model is NOT bundled in the repo (126 MB).  The path is read
# from the FASTTEXT_MODEL_PATH env var and falls back to the location
# expected inside the Docker container.
_FASTTEXT_MODEL_PATH = os.getenv(
    "FASTTEXT_MODEL_PATH",
    "/app/models/lid.176.bin",
)

# Supported language codes returned by fastText that we care about.
LANG_GUJARATI = "gu"
LANG_HINDI = "hi"
LANG_ENGLISH = "en"
LANG_UNKNOWN = "unknown"

#: Labels we surface to callers
SUPPORTED_LANGS = {LANG_GUJARATI, LANG_HINDI, LANG_ENGLISH}


# ---------------------------------------------------------------------------
# Lazy singletons
# ---------------------------------------------------------------------------

_fasttext_model = None
_xlit_engine = None


def _get_fasttext():
    """Return the fastText model, loading it on first call."""
    global _fasttext_model
    if _fasttext_model is None:
        try:
            import fasttext  # type: ignore

            _fasttext_model = fasttext.load_model(_FASTTEXT_MODEL_PATH)
            logger.info("fastText model loaded from %s", _FASTTEXT_MODEL_PATH)
        except Exception as exc:
            logger.warning(
                "fastText model unavailable (%s); language detection disabled.", exc
            )
    return _fasttext_model


def _get_xlit():
    """Return the IndicXlit engine, loading it on first call."""
    global _xlit_engine
    if _xlit_engine is None:
        try:
            from xlit import XlitEngine  # type: ignore

            _xlit_engine = XlitEngine(src_script="en", beam_width=4)
            logger.info("IndicXlit transliteration engine loaded.")
        except Exception as exc:
            logger.warning(
                "IndicXlit unavailable (%s); transliteration disabled.", exc
            )
    return _xlit_engine


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def detect_language(text: str) -> str:
    """Detect the dominant language of *text*.

    Returns one of ``"gu"``, ``"hi"``, ``"en"``, or ``"unknown"``.

    Uses fastText lid.176.bin.  If the model is not available (e.g. in CI
    environments without the model file) it falls back to ``"unknown"``.

    Parameters
    ----------
    text:
        Raw input; should be at least a few tokens long for reliable results.
    """
    if not text or not text.strip():
        return LANG_UNKNOWN

    model = _get_fasttext()
    if model is None:
        return LANG_UNKNOWN

    # fastText expects a single-line string
    clean = text.replace("\n", " ").strip()
    try:
        labels, scores = model.predict(clean, k=1)
        # labels are like "__label__en"
        lang_code = labels[0].replace("__label__", "")
        return lang_code if lang_code in SUPPORTED_LANGS else lang_code
    except Exception as exc:
        logger.debug("fastText prediction error: %s", exc)
        return LANG_UNKNOWN


def normalise_text(text: str) -> str:
    """Apply Unicode NFC normalisation and strip leading/trailing whitespace.

    Also removes NUL bytes (\\x00) which PostgreSQL rejects and can appear in
    PDF-extracted text from malformed or scanned documents.

    Parameters
    ----------
    text:
        Raw text from OCR or user input.
    """
    if not text:
        return ""
    # Strip NUL bytes before NFC normalisation
    text = text.replace("\x00", "")
    return unicodedata.normalize("NFC", text).strip()


def transliterate_romanised_gujarati(text: str) -> str:
    """Transliterate Romanised Gujarati (Roman-script Gujarati) to native script.

    Many FIRs mix native Gujarati script with phonetically-spelled Gujarati
    written in the Roman alphabet.  This function passes the *entire* string
    through IndicXlit which handles mixed input gracefully.

    If IndicXlit is unavailable the original text is returned unchanged.

    Parameters
    ----------
    text:
        Input text that may contain Romanised Gujarati.
    """
    engine = _get_xlit()
    if engine is None:
        return text
    try:
        result = engine.translit_sentence(text, lang_code="gu")
        return result if isinstance(result, str) else text
    except Exception as exc:
        logger.debug("IndicXlit transliteration error: %s", exc)
        return text


def preprocess_text(
    text: str,
    *,
    transliterate: bool = False,
    detected_lang: Optional[str] = None,
) -> dict:
    """Full preprocessing pipeline: normalise → detect language → optionally transliterate.

    Returns a dict with the keys required by the NLP metadata JSONB column:

    .. code-block:: python

        {
            "normalised": str,          # NFC-normalised text
            "detected_lang": str,       # e.g. "gu", "en", "unknown"
            "transliterated": str|None, # native-script version if transliterate=True
        }

    Parameters
    ----------
    text:
        Raw input text (narrative or full FIR text).
    transliterate:
        Whether to run IndicXlit on the normalised text.
    detected_lang:
        Pre-computed language code; if supplied detection is skipped.
    """
    normalised = normalise_text(text)
    lang = detected_lang if detected_lang else detect_language(normalised)
    transliterated: Optional[str] = None
    if transliterate:
        transliterated = transliterate_romanised_gujarati(normalised)

    return {
        "normalised": normalised,
        "detected_lang": lang,
        "transliterated": transliterated,
    }
