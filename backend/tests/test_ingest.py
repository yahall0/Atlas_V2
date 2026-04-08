"""
OCR extraction test harness with fir_023 fixture.

Tests the ingestion endpoint and FIR parser with sample eGujCop OCR output.
Parser tests require backend/app/ingestion/fir_parser.py to be present;
they are skipped automatically if the module is not yet available.
"""

import importlib
import re
import uuid
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

# Check if ingestion modules are available
try:
    _has_parser = importlib.util.find_spec("app.ingestion.fir_parser") is not None
except ModuleNotFoundError:
    _has_parser = False

_has_ingest_route = any(
    "/ingest" in str(getattr(r, "path", "")) for r in app.routes
)

skip_no_parser = pytest.mark.skipif(
    not _has_parser,
    reason="app.ingestion.fir_parser not available yet",
)
skip_no_ingest = pytest.mark.skipif(
    not _has_ingest_route,
    reason="/api/v1/ingest route not registered yet",
)

# Minimal valid PDF (single blank page, spec-compliant)
MINIMAL_PDF = (
    b"%PDF-1.0\n"
    b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
    b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
    b"3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R>>endobj\n"
    b"xref\n0 4\n"
    b"0000000000 65535 f \n"
    b"0000000009 00000 n \n"
    b"0000000058 00000 n \n"
    b"0000000115 00000 n \n"
    b"trailer<</Size 4/Root 1 0 R>>\n"
    b"startxref\n190\n%%EOF"
)


def _mock_create_fir(conn, fir_data):
    """Return a fake FIR record for DB-free testing."""
    return {
        "id": str(uuid.uuid4()),
        "fir_number": fir_data.get("fir_number"),
        "police_station": fir_data.get("police_station"),
        "district": fir_data.get("district"),
        "fir_date": fir_data.get("fir_date"),
        "occurrence_start": None,
        "occurrence_end": None,
        "primary_act": fir_data.get("primary_act"),
        "primary_sections": fir_data.get("primary_sections", []),
        "narrative": fir_data.get("narrative", ""),
        "raw_text": fir_data.get("raw_text", ""),
        "source_system": fir_data.get("source_system", "pdf_upload"),
        "created_at": datetime.now(timezone.utc),
        "complainants": [],
        "accused": [],
    }


# ─────────────────────────────────────────────
# Endpoint tests
# ─────────────────────────────────────────────

@skip_no_ingest
def test_upload_pdf_returns_201(tmp_path):
    """Upload a minimal valid PDF to POST /api/v1/ingest -> 201."""
    pdf_file = tmp_path / "test.pdf"
    pdf_file.write_bytes(MINIMAL_PDF)

    with (
        patch("app.api.v1.ingest.get_connection", return_value=MagicMock()),
        patch("app.api.v1.ingest.create_fir", side_effect=_mock_create_fir),
    ):
        with open(pdf_file, "rb") as f:
            resp = client.post(
                "/api/v1/ingest",
                files={"file": ("test.pdf", f, "application/pdf")},
            )
    assert resp.status_code == 201
    data = resp.json()
    assert "narrative" in data
    assert "id" in data


@skip_no_ingest
def test_upload_non_pdf_returns_415(tmp_path):
    """Upload a .txt file -> 415 Unsupported Media Type."""
    txt_file = tmp_path / "test.txt"
    txt_file.write_text("not a pdf")
    with open(txt_file, "rb") as f:
        resp = client.post(
            "/api/v1/ingest",
            files={"file": ("test.txt", f, "text/plain")},
        )
    assert resp.status_code == 415


# ─────────────────────────────────────────────
# FIR parser unit tests
# ─────────────────────────────────────────────

@skip_no_parser
def test_fir_parser_district_extraction(sample_ocr_text):
    from app.ingestion.fir_parser import parse_fir_text
    result = parse_fir_text(sample_ocr_text)
    district = result.get("district") or ""
    assert "અમદાવાદ" in district


@skip_no_parser
def test_fir_parser_fir_number(sample_ocr_text):
    from app.ingestion.fir_parser import parse_fir_text
    result = parse_fir_text(sample_ocr_text)
    fir_num = result.get("fir_number") or ""
    assert "11192050250" in fir_num


@skip_no_parser
def test_fir_parser_sections(sample_ocr_text):
    from app.ingestion.fir_parser import parse_fir_text
    result = parse_fir_text(sample_ocr_text)
    sections = result.get("primary_sections", [])
    section_str = ",".join(sections)
    assert "305" in section_str
    assert "331" in section_str


@skip_no_parser
def test_fir_parser_complainant(sample_ocr_text):
    from app.ingestion.fir_parser import parse_fir_text
    result = parse_fir_text(sample_ocr_text)
    name = result.get("complainant_name") or ""
    assert len(name) > 0


@skip_no_parser
def test_fir_parser_stolen_property_total(sample_ocr_text):
    from app.ingestion.fir_parser import parse_fir_text
    result = parse_fir_text(sample_ocr_text)
    stolen = result.get("stolen_property", {})
    total = str(stolen.get("total_value") or "")
    assert "178500" in total.replace(",", "").replace(" ", "")


# ─────────────────────────────────────────────
# Gujarati numeral conversion tests
# ─────────────────────────────────────────────

def test_gujarati_numeral_conversion():
    """Test basic Gujarati numeral to ASCII conversion."""
    guj_digits = "૦૧૨૩૪૫૬૭૮૯"
    ascii_digits = "0123456789"
    table = str.maketrans(guj_digits, ascii_digits)

    test_input = "રૂ.૫૦,૦૦૦"
    converted = test_input.translate(table)
    numbers_only = re.sub(r"[^\d]", "", converted)
    assert numbers_only == "50000"


def test_gujarati_fir_number_conversion():
    """Test FIR number Gujarati to ASCII."""
    guj_digits = "૦૧૨૩૪૫૬૭૮૯"
    ascii_digits = "0123456789"
    table = str.maketrans(guj_digits, ascii_digits)

    fir_num = "૧૧૧૯૨૦૫૦૨૫૦૦૧૦"
    assert fir_num.translate(table) == "11192050250010"
