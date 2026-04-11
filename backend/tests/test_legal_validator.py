"""Legal cross-reference validation engine tests.

Tests cover:
- Each of the 7 validation rules individually
- Section lookup API endpoint
- Validation with no linked FIR (partial validation)
- RBAC enforcement (IO cannot trigger validate, SHO can)
- Legal DB helper functions
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.rbac import get_current_user as _rbac_get_current_user
from app.legal_validator import LegalCrossReferenceValidator

client = TestClient(app)
validator = LegalCrossReferenceValidator()


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


def _sho_user():
    return {
        "username": "test_sho",
        "role": "SHO",
        "district": "Ahmedabad",
        "full_name": "Test SHO",
    }


def _io_user():
    return {
        "username": "test_io",
        "role": "IO",
        "district": "Ahmedabad",
        "full_name": "Test IO",
    }


@pytest.fixture(autouse=True)
def _auth_admin():
    app.dependency_overrides[_rbac_get_current_user] = _admin_user
    yield
    app.dependency_overrides.pop(_rbac_get_current_user, None)


# ─────────────────────────────────────────────────────────────────────────────
# Helper builders
# ─────────────────────────────────────────────────────────────────────────────

def _make_cs(charges, evidence=None, filing_date="2025-01-15"):
    """Build a minimal chargesheet data dict."""
    return {
        "id": str(uuid.uuid4()),
        "fir_id": None,
        "charges_json": charges,
        "evidence_json": evidence or [],
        "filing_date": filing_date,
    }


def _make_fir(sections, fir_date="2025-01-10", act="IPC"):
    """Build a minimal FIR data dict."""
    return {
        "id": str(uuid.uuid4()),
        "fir_number": "TEST/2025/001",
        "primary_sections": sections,
        "primary_act": act,
        "fir_date": fir_date,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Rule 1 — Section Mismatch
# ─────────────────────────────────────────────────────────────────────────────


class TestRule1SectionMismatch:
    def test_new_section_in_cs_not_in_fir(self):
        """CS has 307, FIR only has 323 -> WARNING for 307."""
        cs = _make_cs([{"section": "307", "act": "IPC"}, {"section": "323", "act": "IPC"}])
        fir = _make_fir(["323"])
        report = validator.validate(cs, fir)

        rule1 = [f for f in report.findings if f.rule_id == "RULE_1"]
        assert len(rule1) >= 1
        assert any("307" in f.section for f in rule1)
        assert all(f.severity == "WARNING" for f in rule1)

    def test_generic_sections_not_flagged(self):
        """Section 34 (common intention) added in CS should not trigger mismatch."""
        cs = _make_cs([{"section": "302", "act": "IPC"}, {"section": "34", "act": "IPC"}])
        fir = _make_fir(["302"])
        report = validator.validate(cs, fir)

        rule1 = [f for f in report.findings if f.rule_id == "RULE_1"]
        assert not any("34" in f.section for f in rule1)


# ─────────────────────────────────────────────────────────────────────────────
# Rule 2 — Dropped Sections
# ─────────────────────────────────────────────────────────────────────────────


class TestRule2DroppedSections:
    def test_section_in_fir_missing_from_cs(self):
        """FIR has 302+201, CS only has 302 -> ERROR for dropped 201."""
        cs = _make_cs([{"section": "302", "act": "IPC"}])
        fir = _make_fir(["302", "201"])
        report = validator.validate(cs, fir)

        rule2 = [f for f in report.findings if f.rule_id == "RULE_2"]
        assert len(rule2) >= 1
        assert any("201" in f.section for f in rule2)
        assert all(f.severity == "ERROR" for f in rule2)


# ─────────────────────────────────────────────────────────────────────────────
# Rule 3 — Invalid Section Combinations
# ─────────────────────────────────────────────────────────────────────────────


class TestRule3InvalidCombinations:
    def test_302_and_304_mutually_exclusive(self):
        """302 + 304 on same chargesheet -> ERROR."""
        cs = _make_cs([
            {"section": "302", "act": "IPC"},
            {"section": "304", "act": "IPC"},
        ])
        report = validator.validate(cs, fir_data=None)

        rule3 = [f for f in report.findings if f.rule_id == "RULE_3"]
        assert len(rule3) >= 1
        assert all(f.severity == "ERROR" for f in rule3)

    def test_non_exclusive_sections_no_error(self):
        """302 + 201 should not trigger mutual exclusion."""
        cs = _make_cs([
            {"section": "302", "act": "IPC"},
            {"section": "201", "act": "IPC"},
        ])
        report = validator.validate(cs, fir_data=None)

        rule3 = [f for f in report.findings if f.rule_id == "RULE_3"]
        assert len(rule3) == 0


# ─────────────────────────────────────────────────────────────────────────────
# Rule 4 — Missing Companion Sections
# ─────────────────────────────────────────────────────────────────────────────


class TestRule4MissingCompanions:
    def test_302_without_201(self):
        """302 charged, 201 absent -> WARNING for missing companion."""
        cs = _make_cs([{"section": "302", "act": "IPC"}])
        report = validator.validate(cs, fir_data=None)

        rule4 = [f for f in report.findings if f.rule_id == "RULE_4"]
        assert any("201" in f.description for f in rule4)
        assert all(f.severity == "WARNING" for f in rule4)

    def test_no_warning_when_companion_present(self):
        """302 + 201 present -> no companion warning for 201."""
        cs = _make_cs([
            {"section": "302", "act": "IPC"},
            {"section": "201", "act": "IPC"},
            {"section": "120B", "act": "IPC"},
        ])
        report = validator.validate(cs, fir_data=None)

        rule4 = [f for f in report.findings if f.rule_id == "RULE_4"]
        assert not any("201" in f.description and "302" in f.section for f in rule4)


# ─────────────────────────────────────────────────────────────────────────────
# Rule 5 — Procedural Gaps
# ─────────────────────────────────────────────────────────────────────────────


class TestRule5ProceduralGaps:
    def test_376_without_164_statement(self):
        """376 charged but no 164 statement in evidence -> CRITICAL."""
        cs = _make_cs(
            [{"section": "376", "act": "IPC"}],
            evidence=[{"type": "Documentary", "description": "FIR copy"}],
        )
        report = validator.validate(cs, fir_data=None)

        rule5 = [f for f in report.findings if f.rule_id == "RULE_5"]
        assert len(rule5) >= 1
        assert any(f.severity == "CRITICAL" for f in rule5)
        assert any("164" in f.description or "magistrate" in f.description.lower() for f in rule5)

    def test_376_with_164_no_critical(self):
        """376 charged with 164 statement present -> no CRITICAL for that procedure."""
        cs = _make_cs(
            [{"section": "376", "act": "IPC"}],
            evidence=[
                {"type": "Documentary", "description": "Statement under section 164 CrPC"},
                {"type": "Medical", "description": "Medical examination report"},
            ],
        )
        report = validator.validate(cs, fir_data=None)

        rule5 = [f for f in report.findings if f.rule_id == "RULE_5"]
        magistrate_findings = [f for f in rule5 if "magistrate" in f.description.lower()]
        assert len(magistrate_findings) == 0


# ─────────────────────────────────────────────────────────────────────────────
# Rule 6 — IPC/BNS Mismatch
# ─────────────────────────────────────────────────────────────────────────────


class TestRule6IPCBNSMismatch:
    def test_ipc_on_post_bns_case(self):
        """IPC sections used on post-July-2024 FIR -> ERROR."""
        cs = _make_cs(
            [{"section": "302", "act": "IPC"}],
            filing_date="2025-01-15",
        )
        fir = _make_fir(["302"], fir_date="2025-01-10")
        report = validator.validate(cs, fir)

        rule6 = [f for f in report.findings if f.rule_id == "RULE_6"]
        assert len(rule6) >= 1
        assert all(f.severity == "ERROR" for f in rule6)

    def test_bns_on_pre_bns_case(self):
        """BNS sections used on pre-July-2024 FIR -> ERROR."""
        cs = _make_cs(
            [{"section": "103", "act": "BNS"}],
            filing_date="2024-03-15",
        )
        fir = _make_fir(["302"], fir_date="2024-03-10")
        report = validator.validate(cs, fir)

        rule6 = [f for f in report.findings if f.rule_id == "RULE_6"]
        assert len(rule6) >= 1

    def test_correct_act_no_error(self):
        """BNS on post-BNS case -> no RULE_6 error."""
        cs = _make_cs(
            [{"section": "103", "act": "BNS"}],
            filing_date="2025-01-15",
        )
        fir = _make_fir(["103"], fir_date="2025-01-10", act="BNS")
        report = validator.validate(cs, fir)

        rule6 = [f for f in report.findings if f.rule_id == "RULE_6"]
        assert len(rule6) == 0


# ─────────────────────────────────────────────────────────────────────────────
# Rule 7 — Evidence Sufficiency
# ─────────────────────────────────────────────────────────────────────────────


class TestRule7EvidenceSufficiency:
    def test_302_without_post_mortem(self):
        """302 charged, no post mortem in evidence -> WARNING."""
        cs = _make_cs(
            [{"section": "302", "act": "IPC"}],
            evidence=[{"type": "Documentary", "description": "FIR copy"}],
        )
        report = validator.validate(cs, fir_data=None)

        rule7 = [f for f in report.findings if f.rule_id == "RULE_7"]
        assert any("post mortem" in f.description.lower() for f in rule7)
        assert all(f.severity == "WARNING" for f in rule7)

    def test_evidence_coverage_below_100(self):
        """Missing evidence should lower coverage percentage."""
        cs = _make_cs(
            [{"section": "302", "act": "IPC"}],
            evidence=[],
        )
        report = validator.validate(cs, fir_data=None)
        report_dict = report.to_dict()
        assert report_dict["summary"]["evidence_coverage_pct"] < 100.0


# ─────────────────────────────────────────────────────────────────────────────
# Validation without linked FIR
# ─────────────────────────────────────────────────────────────────────────────


class TestNoLinkedFIR:
    def test_partial_validation_no_fir(self):
        """Without FIR, rules 1 and 2 are skipped but 3-7 still run."""
        cs = _make_cs([
            {"section": "302", "act": "IPC"},
            {"section": "304", "act": "IPC"},
        ])
        report = validator.validate(cs, fir_data=None)

        rule_ids = {f.rule_id for f in report.findings}
        # Rules 1 and 2 should NOT be present
        assert "RULE_1" not in rule_ids
        assert "RULE_2" not in rule_ids
        # Rule 3 should fire (302+304 exclusive)
        assert "RULE_3" in rule_ids

    def test_overall_status_reflects_severity(self):
        """Overall status should be the highest severity found."""
        cs = _make_cs(
            [{"section": "376", "act": "IPC"}],
            evidence=[],
        )
        report = validator.validate(cs, fir_data=None)
        assert report.overall_status == "critical"


# ─────────────────────────────────────────────────────────────────────────────
# Legal DB helper tests
# ─────────────────────────────────────────────────────────────────────────────


class TestLegalDB:
    def test_section_lookup_302(self):
        from app.legal_db import get_section
        entry = get_section("302", "ipc")
        assert entry is not None
        assert entry["title"] == "Murder"
        assert entry["category"] == "murder"

    def test_bns_equivalent(self):
        from app.legal_db import get_bns_equivalent
        bns = get_bns_equivalent("302")
        assert bns is not None
        assert "103" in bns

    def test_ipc_equivalent(self):
        from app.legal_db import get_ipc_equivalent
        ipc = get_ipc_equivalent("103(1)")
        assert ipc == "302"

    def test_mandatory_evidence_302(self):
        from app.legal_db import get_mandatory_evidence
        evidence = get_mandatory_evidence("302")
        assert "post_mortem_report" in evidence

    def test_unknown_section_returns_none(self):
        from app.legal_db import get_section
        assert get_section("9999") is None


# ─────────────────────────────────────────────────────────────────────────────
# API endpoint tests
# ─────────────────────────────────────────────────────────────────────────────


class TestSectionLookupAPI:
    def test_lookup_302_ipc(self):
        resp = client.get("/api/v1/validate/sections/lookup?section=302&act=ipc")
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "Murder"
        assert data["equivalent"]["bns_section"] is not None
        assert "post_mortem_report" in data["mandatory_evidence"]

    def test_lookup_unknown_section(self):
        resp = client.get("/api/v1/validate/sections/lookup?section=9999&act=ipc")
        assert resp.status_code == 404

    def test_lookup_bns_section(self):
        resp = client.get("/api/v1/validate/sections/lookup?section=103(1)&act=bns")
        assert resp.status_code == 200
        data = resp.json()
        assert data["equivalent"]["ipc_section"] == "302"


class TestValidateAPIRBAC:
    def test_io_cannot_trigger_validate(self):
        """IO role should be rejected for validation (minimum SHO)."""
        app.dependency_overrides[_rbac_get_current_user] = _io_user
        resp = client.post(f"/api/v1/validate/chargesheet/{uuid.uuid4()}")
        assert resp.status_code == 403

    def test_sho_can_trigger_validate(self):
        """SHO role should be allowed to trigger validation."""
        app.dependency_overrides[_rbac_get_current_user] = _sho_user
        cs_id = str(uuid.uuid4())
        mock_cs = {
            "id": cs_id,
            "fir_id": None,
            "charges_json": [{"section": "420", "act": "IPC"}],
            "evidence_json": [],
            "filing_date": "2023-06-15",
        }
        with (
            patch("app.api.v1.validate.get_connection", return_value=MagicMock()),
            patch("app.api.v1.validate.get_chargesheet_by_id", return_value=mock_cs),
            patch("app.api.v1.validate.create_validation_report",
                  side_effect=lambda conn, data: {
                      "id": str(uuid.uuid4()),
                      **data,
                      "created_at": datetime.now(timezone.utc),
                      "updated_at": datetime.now(timezone.utc),
                  }),
        ):
            resp = client.post(f"/api/v1/validate/chargesheet/{cs_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert "overall_status" in data
        assert "findings" in data

    def test_io_can_lookup_sections(self):
        """IO role should be allowed to use section lookup."""
        app.dependency_overrides[_rbac_get_current_user] = _io_user
        resp = client.get("/api/v1/validate/sections/lookup?section=302&act=ipc")
        assert resp.status_code == 200


class TestValidateAPIEndpoint:
    def test_validate_chargesheet_not_found(self):
        with (
            patch("app.api.v1.validate.get_connection", return_value=MagicMock()),
            patch("app.api.v1.validate.get_chargesheet_by_id", return_value=None),
        ):
            resp = client.post(f"/api/v1/validate/chargesheet/{uuid.uuid4()}")
        assert resp.status_code == 404

    def test_get_report_not_found(self):
        with (
            patch("app.api.v1.validate.get_connection", return_value=MagicMock()),
            patch("app.api.v1.validate.get_validation_report_by_id", return_value=None),
        ):
            resp = client.get(f"/api/v1/validate/report/{uuid.uuid4()}")
        assert resp.status_code == 404
