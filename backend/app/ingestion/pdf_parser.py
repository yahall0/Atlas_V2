"""PDF text extraction using pdfplumber with OCR fallback.

Strategy
--------
1. Try pdfplumber (fast; works for text-based / digital PDFs).
2. If the result is too short (< 50 non-whitespace chars), the PDF is likely
   image-based (scanned).  Fall back to OCR:
      a. pdf2image + pytesseract at 300 DPI (preferred — better quality).
      b. PyMuPDF + pytesseract at 200 DPI (fallback when poppler is absent).

OCR language: eng+guj (English + Gujarati) for eGujCop FIRs.
"""

from __future__ import annotations

import io
import logging
import re

import fitz  # PyMuPDF
import pdfplumber
import pytesseract
from PIL import Image

logger = logging.getLogger(__name__)

# Minimum non-whitespace characters before we trust pdfplumber's output.
_MIN_TEXT_LENGTH = 50

# Tesseract language pack — English + Gujarati
_OCR_LANG = "eng+guj"

# Indic Unicode range — Devanagari (U+0900) through Gujarati (U+0AFF)
_INDIC_RE = re.compile(r'[\u0900-\u0AFF]')

# Common English keywords found in eGujCop FIR PDFs with standard encoding.
_FIR_ANCHOR_RE = re.compile(
    r'\b(?:F\.?I\.?R|First\s+Information|Police\s+Station|District|'
    r'Complainant|Accused|Section\s+\d|Occurrence|Under\s+Section)\b',
    re.IGNORECASE,
)

# PyMuPDF fallback resolution (DPI)
_DPI = 200


def _clean_text(text: str) -> str:
    """Normalize raw OCR output before joining pages."""
    text = re.sub(r"[ \t]+", " ", text)       # collapse horizontal space
    text = re.sub(r"\n{3,}", "\n\n", text)     # max 2 consecutive newlines
    text = text.replace("\u0964\u0964", "")    # remove Devanagari double-danda artefact
    text = text.replace("€", "")              # stray euro-sign artefact
    return text.strip()


def _looks_garbled(text: str) -> bool:
    """Detect garbled text from custom-font-encoded Indian language PDFs.

    Many Indian government PDFs (eGujCop, etc.) embed custom fonts that map
    Gujarati glyphs to Latin codepoints internally.  PDF viewers render the
    correct shapes because they use the embedded font outlines, but text
    extraction tools (pdfplumber, PyMuPDF) read the underlying codepoints
    and produce gibberish Latin text.

    Returns ``True`` when the text appears garbled so the caller can fall
    back to OCR (which reads visual glyphs, not codepoints).
    """
    # A real Gujarati FIR will have dozens to hundreds of Indic characters.
    indic_chars = len(_INDIC_RE.findall(text))
    if indic_chars >= 20:
        return False

    # No meaningful Indic chars — check for recognisable English FIR
    # structure (plausible English-only or bilingual FIR).
    anchor_hits = len(_FIR_ANCHOR_RE.findall(text))
    if anchor_hits >= 3:
        return False

    # Neither Indic characters nor English FIR anchors → garbled.
    return True


def _ocr_pdf(file_bytes: bytes) -> str:
    """OCR primary path: pdf2image at 300 DPI → PyMuPDF 200 DPI fallback.

    pdf2image (poppler) renders pages at higher fidelity which substantially
    improves Tesseract accuracy on eGujCop scanned FIRs.  If poppler is not
    installed (e.g. on bare Windows), the function falls back to PyMuPDF.
    """
    try:
        from pdf2image import convert_from_bytes  # lazy import — optional dep

        images = convert_from_bytes(file_bytes, dpi=300)
        pages_text: list[str] = []
        for page_num, img in enumerate(images, 1):
            raw = pytesseract.image_to_string(img, lang=_OCR_LANG, config="--psm 6")
            pages_text.append(_clean_text(raw))
            logger.debug("pdf2image OCR page %d: %d chars.", page_num, len(raw))
        return "\n\n".join(pages_text).strip()

    except Exception as exc:
        logger.warning("pdf2image OCR unavailable (%s); falling back to PyMuPDF.", exc)
        return _ocr_pdf_pymupdf(file_bytes)


def _ocr_pdf_pymupdf(file_bytes: bytes) -> str:
    """Fallback OCR using PyMuPDF at 200 DPI (no poppler required)."""
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    pages_text: list[str] = []
    matrix = fitz.Matrix(_DPI / 72, _DPI / 72)  # 72 dpi is PyMuPDF's base

    for page_num, page in enumerate(doc):
        try:
            pix = page.get_pixmap(matrix=matrix, colorspace=fitz.csRGB)
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            text = pytesseract.image_to_string(img, lang=_OCR_LANG)
            pages_text.append(_clean_text(text))
            logger.debug("PyMuPDF OCR page %d: %d chars.", page_num + 1, len(text))
        except Exception:
            logger.error("OCR failed on page %d.", page_num + 1, exc_info=True)
            pages_text.append("")

    doc.close()
    return "\n\n".join(pages_text).strip()


def extract_text_from_pdf(file_bytes: bytes) -> str:
    """Extract plain text from a PDF supplied as raw bytes.

    Tries pdfplumber first.  Falls back to OCR (PyMuPDF + pytesseract) when
    the extracted text is below ``_MIN_TEXT_LENGTH`` non-whitespace characters
    (characteristic of scanned / image-based PDFs).

    Returns an empty string if both methods fail.
    """
    # ── Step 1: pdfplumber (text-based PDFs) ─────────────────────────────────
    try:
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            pages_text = [page.extract_text() or "" for page in pdf.pages]
            text = "\n".join(pages_text).strip()

        real_chars = len(text.replace(" ", "").replace("\n", ""))
        logger.debug("pdfplumber: %d real chars extracted.", real_chars)

        if real_chars >= _MIN_TEXT_LENGTH:
            if _looks_garbled(text):
                logger.info(
                    "pdfplumber text appears garbled (custom font encoding); "
                    "falling back to OCR.",
                )
            else:
                return text
        else:
            logger.info(
                "pdfplumber returned only %d real chars — falling back to OCR.",
                real_chars,
            )
    except Exception:
        logger.error("pdfplumber failed; falling back to OCR.", exc_info=True)

    # ── Step 2: OCR fallback (scanned / image PDFs) ──────────────────────────
    try:
        text = _ocr_pdf(file_bytes)
        logger.info("OCR complete: %d chars extracted.", len(text))
        return text
    except Exception:
        logger.error("OCR also failed.", exc_info=True)
        return ""
