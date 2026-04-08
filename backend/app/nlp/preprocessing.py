"""IndicBERT tokeniser wrapper and tokenisation helpers.

This module owns the ``IndicBERTPreprocessor`` class which wraps the
HuggingFace tokeniser for ``ai4bharat/indic-bert``.  The tokeniser is
loaded lazily on first use so that importing this module does not force a
network request at startup.

IndicNLP sentence tokenisation is used when breaking a long narrative
into sentences before feeding individual sentences to the tokeniser (useful
for fine-tuning and inference on large texts).
"""

from __future__ import annotations

import logging
import os
from functools import lru_cache
from typing import Optional

logger = logging.getLogger(__name__)

_INDIC_BERT_MODEL = os.getenv("INDIC_BERT_MODEL", "ai4bharat/indic-bert")
_CACHE_DIR = os.getenv("TRANSFORMERS_CACHE", "/transformers_cache")

_tokenizer = None


def _get_tokenizer():
    """Return the IndicBERT tokeniser, loading it on first call."""
    global _tokenizer
    if _tokenizer is None:
        try:
            from transformers import AutoTokenizer  # type: ignore

            _tokenizer = AutoTokenizer.from_pretrained(
                _INDIC_BERT_MODEL,
                cache_dir=_CACHE_DIR,
            )
            logger.info("IndicBERT tokeniser loaded from %s", _INDIC_BERT_MODEL)
        except Exception as exc:
            logger.warning(
                "IndicBERT tokeniser unavailable (%s); tokenisation disabled.", exc
            )
    return _tokenizer


# ---------------------------------------------------------------------------
# IndicNLP helpers
# ---------------------------------------------------------------------------


def _split_sentences_indic(text: str, lang: str = "gu") -> list[str]:
    """Split *text* into sentences using IndicNLP.

    Falls back to splitting on '.' if IndicNLP is not installed.
    """
    try:
        from indicnlp.tokenize import sentence_tokenize  # type: ignore

        return sentence_tokenize.sentence_split(text, lang=lang)
    except ImportError:
        logger.debug("indicnlp not installed; falling back to naive sentence split.")
        return [s.strip() for s in text.split(".") if s.strip()]
    except Exception as exc:
        logger.debug("IndicNLP sentence split error: %s", exc)
        return [text]


# ---------------------------------------------------------------------------
# Public class
# ---------------------------------------------------------------------------


class IndicBERTPreprocessor:
    """Preprocessing pipeline for IndicBERT input.

    Attributes
    ----------
    max_length:
        Maximum token sequence length passed to the tokeniser (default 512).
    """

    def __init__(self, max_length: int = 512) -> None:
        self.max_length = max_length

    @property
    def tokenizer(self):
        return _get_tokenizer()

    def tokenize(self, text: str) -> Optional[dict]:
        """Tokenise *text* for IndicBERT inference.

        Returns a dict suitable for ``model(**inputs)`` or ``None`` if the
        tokeniser is unavailable.

        Parameters
        ----------
        text:
            Pre-processed (NFC-normalised) input text.
        """
        tok = self.tokenizer
        if tok is None:
            return None
        try:
            return tok(
                text,
                max_length=self.max_length,
                padding="max_length",
                truncation=True,
                return_tensors="pt",
            )
        except Exception as exc:
            logger.warning("Tokenisation failed: %s", exc)
            return None

    def split_sentences(self, text: str, lang: str = "gu") -> list[str]:
        """Split *text* into sentences using IndicNLP.

        Parameters
        ----------
        text:
            Long narrative string.
        lang:
            ISO-639-1 language code (default ``"gu"`` for Gujarati).
        """
        return _split_sentences_indic(text, lang=lang)

    def truncate_to_fit(self, text: str) -> str:
        """Return the longest prefix of *text* that fits within *max_length* tokens.

        Useful when a FIR narrative exceeds 512 tokens — we keep as much text as
        possible without hitting the hard truncation boundary silently.

        Parameters
        ----------
        text:
            Input text (NFC-normalised).
        """
        tok = self.tokenizer
        if tok is None:
            return text

        tokens = tok.encode(text, add_special_tokens=True)
        if len(tokens) <= self.max_length:
            return text

        # Drop the last token (EOS) before truncating, then re-decode
        truncated_ids = tokens[: self.max_length - 1]
        return tok.decode(truncated_ids, skip_special_tokens=True)


# ---------------------------------------------------------------------------
# Module-level convenience wrapper
# ---------------------------------------------------------------------------

_default_preprocessor: Optional[IndicBERTPreprocessor] = None


def full_pipeline(text: str, lang: str = "gu") -> dict:
    """Run the full preprocessing pipeline on *text* and return a metadata dict.

    Steps:
    1. Split into sentences (IndicNLP).
    2. Tokenise the full text (IndicBERT tokeniser).
    3. Report token count.

    The dict returned is suitable for merging into the ``nlp_metadata``
    JSONB column entry.

    Parameters
    ----------
    text:
        NFC-normalised input text.
    lang:
        ISO-639-1 language code to use for sentence splitting.
    """
    global _default_preprocessor
    if _default_preprocessor is None:
        _default_preprocessor = IndicBERTPreprocessor()

    pp = _default_preprocessor
    sentences = pp.split_sentences(text, lang=lang)
    tok_inputs = pp.tokenize(text)
    token_count: Optional[int] = None
    if tok_inputs is not None:
        token_count = int(tok_inputs["input_ids"].shape[-1])

    return {
        "sentence_count": len(sentences),
        "token_count": token_count,
        "sentences": sentences[:5],  # store first 5 sentences as preview
    }
