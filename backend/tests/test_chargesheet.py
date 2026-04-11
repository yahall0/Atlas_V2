"""Charge-sheet ingestion and API tests.

Tests cover:
- Chargesheet parser on two embedded sample texts (English + Gujarati-mixed)
- All API endpoints (upload, get, list, review) with RBAC enforcement
- FIR linkage when fir_reference_number matches an existing FIR
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.rbac import get_current_user as _rbac_get_current_user

client = TestClient(app)

# Minimal valid PDF (single blank page)
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

# ─────────────────────────────────────────────────────────────────────────────
# Sample charge-sheet texts
# ─────────────────────────────────────────────────────────────────────────────

SAMPLE_CHARGESHEET_ENGLISH = """
IN THE COURT OF THE JUDICIAL MAGISTRATE FIRST CLASS, AHMEDABAD

CHARGE-SHEET No.: CS/11192050250010/2026

FIR No.: 11192050250010
Police Station: Navrangpura, District: Ahmedabad
U/S: 303, 34 BNS
Filed Date: 15/03/2026

INVESTIGATION OFFICER:
Investigation Officer: PSI R.K. Sharma, Navrangpura Police Station

ACCUSED PERSONS:
1. Name: Rajesh Kumar Patel
   Age: 32
   Address: 45 MG Road, Navrangpura, Ahmedabad
   Role: Primary accused

2. Name: Sunil Bhatt
   Age: 28
   Address: 12 SG Highway, Ahmedabad
   Role: Accomplice

CHARGE:
Section 303 BNS - Theft of moveable property
Section 34 BNS - Common intention

EVIDENCE ON RECORD:
1. Original FIR copy - Documentary - collected
2. CCTV footage from premises - Digital - pending
3. Fingerprint analysis report - Forensic - collected
4. Stolen property recovery panchnama - Documentary - collected

WITNESS SCHEDULE:
1. Kavita Ramesh - Complainant - Filed the original complaint on 06/04/2026
2. Sunil Bhai Patel - Eye-witness - Saw the accused at the scene
3. PC Amit Sharma (3412) - IO - Conducted the investigation

IO CERTIFICATION:
I certify that the investigation has been completed.
"""

SAMPLE_CHARGESHEET_MIXED = """
IN THE COURT OF THE METROPOLITAN MAGISTRATE, SURAT

ચાર્જશીટ નં.: CS/2026/SURAT/042

F.I.R. No. SURAT/2026/0421
P.S.: Adajan, District: Surat
કલમ 420, 34 IPC
તારીખ: 20/02/2026

તપાસ અધિકારી: Inspector M.L. Desai

Accused Persons:
1. Name: Ramesh Desai
   Age: 45
   Address: Textile Market, Ring Road, Surat

Sections:
Sec. 420 IPC - Cheating
Section 34 IPC - Common intention

Evidence List:
1. Bank transaction records - Documentary - collected
2. WhatsApp chat screenshots - Digital - collected

Witnesses:
1. Meera Shah - Complainant - Deposited money for job promise
2. Bank Manager Patel - Expert - Confirmed fraudulent transactions

VERIFICATION:
Investigation completed as per procedure.
"""


# ─────────────────────────────────────────────────────────────────────────────
# Auth fixtures
# ─────────────────────────────────────────────────────────────────────────────

def _admin_user():
    return {
        "username": "test_admin",
        "role": "ADMIN",
        "district": "Ahmedabad",
        "full_name": "Test Admin",
    }


def _io_user():
    return {
        "username": "test_io",
        "role": "IO",
        "district": "Ahmedabad",
        "full_name": "Test IO",
    }


def _readonly_user():
    return {
        "username": "test_readonly",
        "role": "READONLY",
        "district": None,
        "full_name": "Test Readonly",
    }


@pytest.fixture(autouse=True)
def _auth_admin():
    """Default: authenticate as ADMIN for all tests."""
    app.dependency_overrides[_rbac_get_current_user] = _admin_user
    yield
    app.dependency_overrides.pop(_rbac_get_current_user, None)


# ─────────────────────────────────────────────────────────────────────────────
# Parser unit tests
# ─────────────────────────────────────────────────────────────────────────────


class TestChargesheetParser:
    """Test parse_chargesheet_text on embedded sample texts."""

    def test_english_fir_reference(self):
        from app.ingestion.chargesheet_parser import parse_chargesheet_text
        result = parse_chargesheet_text(SAMPLE_CHARGESHEET_ENGLISH)
        assert result["fir_reference_number"] is not None
        assert "11192050250010" in result["fir_reference_number"]

    def test_english_court_name(self):
        from app.ingestion.chargesheet_parser import parse_chargesheet_text
        result = parse_chargesheet_text(SAMPLE_CHARGESHEET_ENGLISH)
        assert result["court_name"] is not None
        assert "JUDICIAL MAGISTRATE" in result["court_name"].upper() or \
               "COURT" in result["court_name"].upper()

    def test_english_filing_date(self):
        from app.ingestion.chargesheet_parser import parse_chargesheet_text
        result = parse_chargesheet_text(SAMPLE_CHARGESHEET_ENGLISH)
        assert result["filing_date"] is not None
        assert "2026" in result["filing_date"]

    def test_english_io(self):
        from app.ingestion.chargesheet_parser import parse_chargesheet_text
        result = parse_chargesheet_text(SAMPLE_CHARGESHEET_ENGLISH)
        assert result["investigation_officer"] is not None
        assert "Sharma" in result["investigation_officer"]

    def test_english_accused_list(self):
        from app.ingestion.chargesheet_parser import parse_chargesheet_text
        result = parse_chargesheet_text(SAMPLE_CHARGESHEET_ENGLISH)
        accused = result.get("accused_list", [])
        assert len(accused) >= 2
        names = [a.get("name", "") for a in accused]
        assert any("Rajesh" in n for n in names)
        assert any("Sunil" in n for n in names)

    def test_english_charges(self):
        from app.ingestion.chargesheet_parser import parse_chargesheet_text
        result = parse_chargesheet_text(SAMPLE_CHARGESHEET_ENGLISH)
        charges = result.get("charge_sections", [])
        sections = [c.get("section") for c in charges]
        assert "303" in sections
        assert "34" in sections

    def test_english_evidence(self):
        from app.ingestion.chargesheet_parser import parse_chargesheet_text
        result = parse_chargesheet_text(SAMPLE_CHARGESHEET_ENGLISH)
        evidence = result.get("evidence_list", [])
        assert len(evidence) >= 3

    def test_english_witnesses(self):
        from app.ingestion.chargesheet_parser import parse_chargesheet_text
        result = parse_chargesheet_text(SAMPLE_CHARGESHEET_ENGLISH)
        witnesses = result.get("witness_schedule", [])
        assert len(witnesses) >= 2

    def test_english_completeness(self):
        from app.ingestion.chargesheet_parser import parse_chargesheet_text
        result = parse_chargesheet_text(SAMPLE_CHARGESHEET_ENGLISH)
        assert result.get("completeness_pct", 0) >= 50.0

    def test_mixed_fir_reference(self):
        from app.ingestion.chargesheet_parser import parse_chargesheet_text
        result = parse_chargesheet_text(SAMPLE_CHARGESHEET_MIXED)
        assert result["fir_reference_number"] is not None
        assert "SURAT" in result["fir_reference_number"] or \
               "0421" in result["fir_reference_number"]

    def test_mixed_charges_ipc(self):
        from app.ingestion.chargesheet_parser import parse_chargesheet_text
        result = parse_chargesheet_text(SAMPLE_CHARGESHEET_MIXED)
        charges = result.get("charge_sections", [])
        sections = [c.get("section") for c in charges]
        assert "420" in sections

    def test_mixed_filing_date(self):
        from app.ingestion.chargesheet_parser import parse_chargesheet_text
        result = parse_chargesheet_text(SAMPLE_CHARGESHEET_MIXED)
        assert result["filing_date"] is not None
        assert "2026" in result["filing_date"]


# ─────────────────────────────────────────────────────────────────────────────
# Mock helpers
# ─────────────────────────────────────────────────────────────────────────────


def _mock_create_chargesheet(conn, data):
    """Return a fake chargesheet record for DB-free testing."""
    return {
        "id": str(uuid.uuid4()),
        "fir_id": data.get("fir_id"),
        "filing_date": None,
        "court_name": data.get("court_name"),
        "accused_json": data.get("accused_json", []),
        "charges_json": data.get("charges_json", []),
        "evidence_json": data.get("evidence_json", []),
        "witnesses_json": data.get("witnesses_json", []),
        "io_name": data.get("io_name"),
        "raw_text": data.get("raw_text", ""),
        "parsed_json": data.get("parsed_json", {}),
        "status": data.get("status", "parsed"),
        "reviewer_notes": None,
        "uploaded_by": data.get("uploaded_by"),
        "district": data.get("district"),
        "police_station": data.get("police_station"),
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }


def _mock_get_chargesheet(conn, cs_id, district=None):
    return {
        "id": cs_id,
        "fir_id": None,
        "filing_date": None,
        "court_name": "Test Court",
        "accused_json": [],
        "charges_json": [],
        "evidence_json": [],
        "witnesses_json": [],
        "io_name": "Test IO",
        "raw_text": "test",
        "parsed_json": {},
        "status": "parsed",
        "reviewer_notes": None,
        "uploaded_by": "test_admin",
        "district": "Ahmedabad",
        "police_station": "Navrangpura",
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }


def _mock_list_chargesheets(conn, **kwargs):
    return [_mock_get_chargesheet(conn, str(uuid.uuid4()))]


def _mock_update_review(conn, cs_id, status, reviewer_notes, reviewer_username):
    row = _mock_get_chargesheet(conn, cs_id)
    row["status"] = status
    row["reviewer_notes"] = reviewer_notes
    return row


# ─────────────────────────────────────────────────────────────────────────────
# API endpoint tests
# ─────────────────────────────────────────────────────────────────────────────


class TestChargesheetAPI:
    """Test charge-sheet API endpoints."""

    def test_health(self):
        resp = client.get("/api/v1/chargesheet/health")
        assert resp.status_code == 200
        assert resp.json()["module"] == "chargesheet"

    def test_upload_returns_202(self, tmp_path):
        pdf_file = tmp_path / "test_cs.pdf"
        pdf_file.write_bytes(MINIMAL_PDF)

        with (
            patch("app.api.v1.chargesheet.get_connection", return_value=MagicMock()),
            patch("app.api.v1.chargesheet.create_chargesheet", side_effect=_mock_create_chargesheet),
            patch("app.api.v1.chargesheet.find_fir_by_number", return_value=None),
        ):
            with open(pdf_file, "rb") as f:
                resp = client.post(
                    "/api/v1/chargesheet/upload",
                    files={"file": ("test_cs.pdf", f, "application/pdf")},
                )
        assert resp.status_code == 202
        data = resp.json()
        assert "id" in data
        assert data["status"] == "parsed"

    def test_upload_rejects_non_pdf(self, tmp_path):
        txt_file = tmp_path / "test.txt"
        txt_file.write_text("not a pdf")
        with open(txt_file, "rb") as f:
            resp = client.post(
                "/api/v1/chargesheet/upload",
                files={"file": ("test.txt", f, "text/plain")},
            )
        assert resp.status_code == 415

    def test_upload_requires_sho_role(self, tmp_path):
        """IO role should be rejected (minimum SHO for upload)."""
        app.dependency_overrides[_rbac_get_current_user] = _io_user

        pdf_file = tmp_path / "test_cs.pdf"
        pdf_file.write_bytes(MINIMAL_PDF)
        with open(pdf_file, "rb") as f:
            resp = client.post(
                "/api/v1/chargesheet/upload",
                files={"file": ("test_cs.pdf", f, "application/pdf")},
            )
        assert resp.status_code == 403

    def test_get_chargesheet(self):
        cs_id = str(uuid.uuid4())
        with (
            patch("app.api.v1.chargesheet.get_connection", return_value=MagicMock()),
            patch("app.api.v1.chargesheet.get_chargesheet_by_id",
                  side_effect=lambda conn, cid, district=None: _mock_get_chargesheet(conn, cid, district)),
        ):
            resp = client.get(f"/api/v1/chargesheet/{cs_id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == cs_id

    def test_get_chargesheet_404(self):
        with (
            patch("app.api.v1.chargesheet.get_connection", return_value=MagicMock()),
            patch("app.api.v1.chargesheet.get_chargesheet_by_id", return_value=None),
        ):
            resp = client.get(f"/api/v1/chargesheet/{uuid.uuid4()}")
        assert resp.status_code == 404

    def test_list_chargesheets(self):
        with (
            patch("app.api.v1.chargesheet.get_connection", return_value=MagicMock()),
            patch("app.api.v1.chargesheet.list_chargesheets", side_effect=_mock_list_chargesheets),
        ):
            resp = client.get("/api/v1/chargesheet/?limit=5")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 1

    def test_list_readonly_allowed(self):
        """READONLY role should be able to list charge-sheets."""
        app.dependency_overrides[_rbac_get_current_user] = _readonly_user
        with (
            patch("app.api.v1.chargesheet.get_connection", return_value=MagicMock()),
            patch("app.api.v1.chargesheet.list_chargesheets", side_effect=_mock_list_chargesheets),
        ):
            resp = client.get("/api/v1/chargesheet/")
        assert resp.status_code == 200

    def test_review_accept(self):
        cs_id = str(uuid.uuid4())
        with (
            patch("app.api.v1.chargesheet.get_connection", return_value=MagicMock()),
            patch("app.api.v1.chargesheet.get_chargesheet_by_id",
                  side_effect=lambda conn, cid, district=None: _mock_get_chargesheet(conn, cid, district)),
            patch("app.api.v1.chargesheet.update_chargesheet_review", side_effect=_mock_update_review),
        ):
            resp = client.patch(
                f"/api/v1/chargesheet/{cs_id}/review",
                json={"status": "reviewed", "reviewer_notes": "Looks good"},
            )
        assert resp.status_code == 200
        assert resp.json()["status"] == "reviewed"

    def test_review_flag(self):
        cs_id = str(uuid.uuid4())
        with (
            patch("app.api.v1.chargesheet.get_connection", return_value=MagicMock()),
            patch("app.api.v1.chargesheet.get_chargesheet_by_id",
                  side_effect=lambda conn, cid, district=None: _mock_get_chargesheet(conn, cid, district)),
            patch("app.api.v1.chargesheet.update_chargesheet_review", side_effect=_mock_update_review),
        ):
            resp = client.patch(
                f"/api/v1/chargesheet/{cs_id}/review",
                json={"status": "flagged", "reviewer_notes": "Sections mismatch"},
            )
        assert resp.status_code == 200
        assert resp.json()["status"] == "flagged"

    def test_review_invalid_status(self):
        cs_id = str(uuid.uuid4())
        resp = client.patch(
            f"/api/v1/chargesheet/{cs_id}/review",
            json={"status": "invalid_status"},
        )
        assert resp.status_code == 422

    def test_review_requires_sho(self):
        """IO role should be rejected for review."""
        app.dependency_overrides[_rbac_get_current_user] = _io_user
        cs_id = str(uuid.uuid4())
        resp = client.patch(
            f"/api/v1/chargesheet/{cs_id}/review",
            json={"status": "reviewed"},
        )
        assert resp.status_code == 403

    def test_list_no_auth_returns_401(self):
        """Without auth, endpoints should return 401."""
        app.dependency_overrides.pop(_rbac_get_current_user, None)
        resp = client.get("/api/v1/chargesheet/")
        assert resp.status_code == 401


# ─────────────────────────────────────────────────────────────────────────────
# FIR linkage test
# ─────────────────────────────────────────────────────────────────────────────


class TestFIRLinkage:
    """Test auto-linkage of charge-sheet to existing FIR."""

    def test_fir_linkage_on_upload(self, tmp_path):
        """When fir_reference_number matches, the chargesheet should link."""
        linked_fir_id = str(uuid.uuid4())

        pdf_file = tmp_path / "cs_link.pdf"
        pdf_file.write_bytes(MINIMAL_PDF)

        # Mock the parser to return a known FIR reference
        mock_parsed = {
            "fir_reference_number": "11192050250010",
            "court_name": "Test Court",
            "filing_date": None,
            "investigation_officer": None,
            "district": "Ahmedabad",
            "police_station": "Navrangpura",
            "accused_list": [],
            "charge_sections": [],
            "evidence_list": [],
            "witness_schedule": [],
            "completeness_pct": 20.0,
            "raw_text": "test",
        }

        with (
            patch("app.api.v1.chargesheet.extract_text_from_pdf", return_value="mock text"),
            patch("app.api.v1.chargesheet.parse_chargesheet_text", return_value=mock_parsed),
            patch("app.api.v1.chargesheet.get_connection", return_value=MagicMock()),
            patch("app.api.v1.chargesheet.find_fir_by_number", return_value=linked_fir_id),
            patch("app.api.v1.chargesheet.create_chargesheet", side_effect=_mock_create_chargesheet),
        ):
            with open(pdf_file, "rb") as f:
                resp = client.post(
                    "/api/v1/chargesheet/upload",
                    files={"file": ("cs.pdf", f, "application/pdf")},
                )

        assert resp.status_code == 202
        data = resp.json()
        assert data["fir_id"] == linked_fir_id
