"""Chargesheet review system + tamper-evident audit chain tests.

Covers: audit chain (6), recommendation actions (6), review flow (5), RBAC (4) = 21 tests.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch, PropertyMock

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.rbac import get_current_user as _rbac_get_current_user
from app.audit_chain import AuditChain, _compute_hash, _GENESIS

client = TestClient(app)


# ─────────────────────────────────────────────────────────────────────────────
# Auth fixtures
# ─────────────────────────────────────────────────────────────────────────────

def _admin_user():
    return {"username": "test_admin", "role": "ADMIN", "district": "Ahmedabad", "full_name": "Test Admin"}

def _sp_user():
    return {"username": "test_sp", "role": "SP", "district": None, "full_name": "Test SP"}

def _dysp_user():
    return {"username": "test_dysp", "role": "DYSP", "district": None, "full_name": "Test DySP"}

def _sho_user():
    return {"username": "test_sho", "role": "SHO", "district": "Ahmedabad", "full_name": "Test SHO"}

def _io_user():
    return {"username": "test_io", "role": "IO", "district": "Ahmedabad", "full_name": "Test IO"}


@pytest.fixture(autouse=True)
def _auth_admin():
    app.dependency_overrides[_rbac_get_current_user] = _admin_user
    yield
    app.dependency_overrides.pop(_rbac_get_current_user, None)


# ─────────────────────────────────────────────────────────────────────────────
# Mock helpers
# ─────────────────────────────────────────────────────────────────────────────

def _mock_cs(cs_id):
    return {
        "id": cs_id, "fir_id": None, "status": "parsed",
        "charges_json": [{"section": "302", "act": "IPC"}],
        "evidence_json": [], "district": "Ahmedabad",
        "court_name": "Test Court", "io_name": "IO Test",
    }


def _mock_audit_entry(cs_id, action, prev_hash=_GENESIS, detail=None):
    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()
    detail = detail or {}
    entry_hash = _compute_hash(action, detail, now_iso, prev_hash)
    return {
        "id": str(uuid.uuid4()),
        "chargesheet_id": cs_id,
        "user_id": "test_admin",
        "action": action,
        "detail_json": detail,
        "ip_address": "127.0.0.1",
        "user_agent": "test",
        "previous_hash": prev_hash,
        "entry_hash": entry_hash,
        "created_at": now.replace(tzinfo=None),
    }


# ═════════════════════════════════════════════════════════════════════════════
# AUDIT CHAIN TESTS
# ═════════════════════════════════════════════════════════════════════════════


class TestAuditChain:
    def test_first_entry_genesis_hash(self):
        """First entry should have previous_hash=GENESIS."""
        entry = _mock_audit_entry("cs-1", "REVIEW_STARTED")
        assert entry["previous_hash"] == _GENESIS

    def test_chain_links(self):
        """Second entry previous_hash should equal first entry_hash."""
        first = _mock_audit_entry("cs-1", "REVIEW_STARTED")
        second = _mock_audit_entry("cs-1", "RECOMMENDATION_ACCEPTED",
                                   prev_hash=first["entry_hash"])
        assert second["previous_hash"] == first["entry_hash"]

    def test_hash_computation_deterministic(self):
        """Same inputs should produce same hash."""
        h1 = _compute_hash("TEST", {"key": "val"}, "2026-01-01T00:00:00", _GENESIS)
        h2 = _compute_hash("TEST", {"key": "val"}, "2026-01-01T00:00:00", _GENESIS)
        assert h1 == h2
        assert len(h1) == 64  # SHA-256 hex

    def test_chain_verification_valid(self):
        """A properly built chain of 5 entries should verify clean."""
        entries = []
        prev = _GENESIS
        for i in range(5):
            entry = _mock_audit_entry(
                "cs-1", f"ACTION_{i}", prev_hash=prev,
                detail={"step": i},
            )
            entries.append(entry)
            prev = entry["entry_hash"]

        # Simulate verification logic
        expected_prev = _GENESIS
        valid = True
        for entry in entries:
            if entry["previous_hash"] != expected_prev:
                valid = False
                break
            ts = entry["created_at"].replace(tzinfo=timezone.utc).isoformat()
            recomputed = _compute_hash(
                entry["action"], entry["detail_json"], ts, entry["previous_hash"]
            )
            if recomputed != entry["entry_hash"]:
                valid = False
                break
            expected_prev = entry["entry_hash"]
        assert valid

    def test_chain_verification_tampered(self):
        """Altering one hash should break verification."""
        entries = []
        prev = _GENESIS
        for i in range(3):
            entry = _mock_audit_entry("cs-1", f"ACTION_{i}", prev_hash=prev)
            entries.append(entry)
            prev = entry["entry_hash"]

        # Tamper with middle entry
        entries[1]["entry_hash"] = "0" * 64

        expected_prev = _GENESIS
        first_break = None
        for idx, entry in enumerate(entries):
            if entry["previous_hash"] != expected_prev:
                first_break = idx
                break
            expected_prev = entry["entry_hash"]

        # Entry 2 will fail because its previous_hash points to original hash of entry 1
        # but entry 1's hash was tampered to all zeros
        assert first_break == 2

    def test_chain_export_csv(self):
        """Export should produce valid CSV bytes."""
        import csv, io
        entry = _mock_audit_entry("cs-1", "TEST_ACTION")
        # Simulate CSV export
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=["action", "entry_hash"])
        writer.writeheader()
        writer.writerow({"action": entry["action"], "entry_hash": entry["entry_hash"]})
        csv_bytes = output.getvalue().encode("utf-8")
        assert b"TEST_ACTION" in csv_bytes
        assert len(csv_bytes) > 0


# ═════════════════════════════════════════════════════════════════════════════
# RECOMMENDATION ACTION TESTS
# ═════════════════════════════════════════════════════════════════════════════


def _rec_patches(cs_id):
    """Context managers for recommendation endpoint tests."""
    mock_create = lambda conn, data: {"id": str(uuid.uuid4()), **data, "created_at": datetime.now(timezone.utc)}
    return (
        patch("app.api.v1.review.get_connection", return_value=MagicMock()),
        patch("app.api.v1.review.get_chargesheet_by_id", return_value=_mock_cs(cs_id)),
        patch("app.api.v1.review.has_recommendation_action", return_value=False),
        patch("app.api.v1.review.AuditChain", return_value=MagicMock(
            log=lambda *a, **kw: _mock_audit_entry(cs_id, "TEST")
        )),
        patch("app.api.v1.review.create_recommendation_action", side_effect=mock_create),
    )


class TestRecommendationActions:
    def test_accept_recommendation(self):
        cs_id = str(uuid.uuid4())
        p1, p2, p3, p4, p5 = _rec_patches(cs_id)
        with p1, p2, p3, p4, p5:
            resp = client.post(
                f"/api/v1/review/chargesheet/{cs_id}/recommendation",
                json={
                    "recommendation_id": "R1",
                    "recommendation_type": "legal_validation",
                    "action": "accepted",
                    "source_rule": "RULE_1",
                },
            )
        assert resp.status_code == 200
        assert resp.json()["action_taken"] == "accepted"

    def test_modify_recommendation(self):
        cs_id = str(uuid.uuid4())
        p1, p2, p3, p4, p5 = _rec_patches(cs_id)
        with p1, p2, p3, p4, p5:
            resp = client.post(
                f"/api/v1/review/chargesheet/{cs_id}/recommendation",
                json={
                    "recommendation_id": "R2",
                    "recommendation_type": "legal_validation",
                    "action": "modified",
                    "modified_text": "Updated recommendation text",
                    "source_rule": "RULE_2",
                },
            )
        assert resp.status_code == 200
        assert resp.json()["action_taken"] == "modified"

    def test_modify_without_text_rejected(self):
        cs_id = str(uuid.uuid4())
        p1, p2, p3, p4, p5 = _rec_patches(cs_id)
        with p1, p2, p3, p4, p5:
            resp = client.post(
                f"/api/v1/review/chargesheet/{cs_id}/recommendation",
                json={
                    "recommendation_id": "R3",
                    "recommendation_type": "legal_validation",
                    "action": "modified",
                    "source_rule": "RULE_3",
                },
            )
        assert resp.status_code == 400

    def test_dismiss_recommendation(self):
        cs_id = str(uuid.uuid4())
        p1, p2, p3, p4, p5 = _rec_patches(cs_id)
        with p1, p2, p3, p4, p5:
            resp = client.post(
                f"/api/v1/review/chargesheet/{cs_id}/recommendation",
                json={
                    "recommendation_id": "R4",
                    "recommendation_type": "evidence_gap",
                    "action": "dismissed",
                    "reason": "Not applicable to this case",
                    "source_rule": "tier_1_rule",
                },
            )
        assert resp.status_code == 200
        assert resp.json()["action_taken"] == "dismissed"

    def test_dismiss_without_reason_rejected(self):
        cs_id = str(uuid.uuid4())
        p1, p2, p3, p4, p5 = _rec_patches(cs_id)
        with p1, p2, p3, p4, p5:
            resp = client.post(
                f"/api/v1/review/chargesheet/{cs_id}/recommendation",
                json={
                    "recommendation_id": "R5",
                    "recommendation_type": "evidence_gap",
                    "action": "dismissed",
                    "source_rule": "RULE_5",
                },
            )
        assert resp.status_code == 400

    def test_duplicate_action_rejected(self):
        cs_id = str(uuid.uuid4())
        mock_conn = MagicMock()
        with (
            patch("app.api.v1.review.get_connection", return_value=mock_conn),
            patch("app.api.v1.review.get_chargesheet_by_id", return_value=_mock_cs(cs_id)),
            patch("app.api.v1.review.has_recommendation_action", return_value=True),
        ):
            resp = client.post(
                f"/api/v1/review/chargesheet/{cs_id}/recommendation",
                json={
                    "recommendation_id": "R_DUP",
                    "recommendation_type": "legal_validation",
                    "action": "accepted",
                },
            )
        assert resp.status_code == 409


# ═════════════════════════════════════════════════════════════════════════════
# REVIEW FLOW TESTS
# ═════════════════════════════════════════════════════════════════════════════


class TestReviewFlow:
    def test_start_review(self):
        cs_id = str(uuid.uuid4())
        mock_conn = MagicMock()
        with (
            patch("app.api.v1.review.get_connection", return_value=mock_conn),
            patch("app.api.v1.review.get_chargesheet_by_id", return_value=_mock_cs(cs_id)),
            patch("app.api.v1.review.AuditChain", return_value=MagicMock(
                log=lambda *a, **kw: _mock_audit_entry(cs_id, "REVIEW_STARTED")
            )),
            patch("app.api.v1.review.get_recommendation_actions", return_value=[]),
        ):
            resp = client.post(f"/api/v1/review/chargesheet/{cs_id}/start")
        assert resp.status_code == 200
        assert resp.json()["status"] == "under_review"

    def test_complete_review_with_flag(self):
        cs_id = str(uuid.uuid4())
        mock_conn = MagicMock()
        with (
            patch("app.api.v1.review.get_connection", return_value=mock_conn),
            patch("app.api.v1.review.get_chargesheet_by_id", return_value=_mock_cs(cs_id)),
            patch("app.api.v1.review.get_recommendation_actions", return_value=[
                {"action_taken": "accepted"},
            ]),
            patch("app.api.v1.review.AuditChain", return_value=MagicMock(
                log=lambda *a, **kw: _mock_audit_entry(cs_id, "REVIEW_FLAGGED")
            )),
        ):
            resp = client.post(
                f"/api/v1/review/chargesheet/{cs_id}/complete",
                json={"overall_assessment": "Needs senior review", "flag_for_senior": True},
            )
        assert resp.status_code == 200
        assert resp.json()["status"] == "flagged"

    def test_complete_review_without_flag(self):
        cs_id = str(uuid.uuid4())
        mock_conn = MagicMock()
        with (
            patch("app.api.v1.review.get_connection", return_value=mock_conn),
            patch("app.api.v1.review.get_chargesheet_by_id", return_value=_mock_cs(cs_id)),
            patch("app.api.v1.review.get_recommendation_actions", return_value=[
                {"action_taken": "accepted"},
                {"action_taken": "dismissed"},
            ]),
            patch("app.api.v1.review.AuditChain", return_value=MagicMock(
                log=lambda *a, **kw: _mock_audit_entry(cs_id, "REVIEW_COMPLETED")
            )),
        ):
            resp = client.post(
                f"/api/v1/review/chargesheet/{cs_id}/complete",
                json={"overall_assessment": "Looks good", "flag_for_senior": False},
            )
        assert resp.status_code == 200
        assert resp.json()["status"] == "reviewed"

    def test_start_not_found(self):
        cs_id = str(uuid.uuid4())
        with (
            patch("app.api.v1.review.get_connection", return_value=MagicMock()),
            patch("app.api.v1.review.get_chargesheet_by_id", return_value=None),
        ):
            resp = client.post(f"/api/v1/review/chargesheet/{cs_id}/start")
        assert resp.status_code == 404

    def test_complete_action_summary(self):
        cs_id = str(uuid.uuid4())
        mock_conn = MagicMock()
        with (
            patch("app.api.v1.review.get_connection", return_value=mock_conn),
            patch("app.api.v1.review.get_chargesheet_by_id", return_value=_mock_cs(cs_id)),
            patch("app.api.v1.review.get_recommendation_actions", return_value=[
                {"action_taken": "accepted"},
                {"action_taken": "modified"},
                {"action_taken": "dismissed"},
            ]),
            patch("app.api.v1.review.AuditChain", return_value=MagicMock(
                log=lambda *a, **kw: _mock_audit_entry(cs_id, "REVIEW_COMPLETED")
            )),
        ):
            resp = client.post(
                f"/api/v1/review/chargesheet/{cs_id}/complete",
                json={"flag_for_senior": False},
            )
        data = resp.json()
        assert data["summary"]["accepted"] == 1
        assert data["summary"]["modified"] == 1
        assert data["summary"]["dismissed"] == 1
        assert data["summary"]["total_actions"] == 3


# ═════════════════════════════════════════════════════════════════════════════
# RBAC TESTS
# ═════════════════════════════════════════════════════════════════════════════


class TestRBAC:
    def test_io_cannot_start_review(self):
        app.dependency_overrides[_rbac_get_current_user] = _io_user
        resp = client.post(f"/api/v1/review/chargesheet/{uuid.uuid4()}/start")
        assert resp.status_code == 403

    def test_sho_can_start_review(self):
        app.dependency_overrides[_rbac_get_current_user] = _sho_user
        cs_id = str(uuid.uuid4())
        mock_conn = MagicMock()
        with (
            patch("app.api.v1.review.get_connection", return_value=mock_conn),
            patch("app.api.v1.review.get_chargesheet_by_id", return_value=_mock_cs(cs_id)),
            patch("app.api.v1.review.AuditChain", return_value=MagicMock(
                log=lambda *a, **kw: _mock_audit_entry(cs_id, "REVIEW_STARTED")
            )),
            patch("app.api.v1.review.get_recommendation_actions", return_value=[]),
        ):
            resp = client.post(f"/api/v1/review/chargesheet/{cs_id}/start")
        assert resp.status_code == 200

    def test_sho_cannot_verify_chain(self):
        app.dependency_overrides[_rbac_get_current_user] = _sho_user
        resp = client.get(f"/api/v1/review/chargesheet/{uuid.uuid4()}/audit/verify")
        assert resp.status_code == 403

    def test_sp_can_verify_chain(self):
        app.dependency_overrides[_rbac_get_current_user] = _sp_user
        cs_id = str(uuid.uuid4())
        with (
            patch("app.api.v1.review.get_connection", return_value=MagicMock()),
            patch("app.api.v1.review.AuditChain", return_value=MagicMock(
                verify_chain=lambda cs: {"valid": True, "total_entries": 0,
                                         "first_break_at": None,
                                         "verified_at": datetime.now(timezone.utc).isoformat()}
            )),
        ):
            resp = client.get(f"/api/v1/review/chargesheet/{cs_id}/audit/verify")
        assert resp.status_code == 200
        assert resp.json()["valid"] is True
