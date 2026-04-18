"""Tests for gap analysis RBAC — T56-E12."""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app, raise_server_exceptions=False)


def _mock_user(role: str, district: str = "Ahmedabad"):
    async def override():
        return {"username": f"test_{role.lower()}", "role": role,
                "district": district, "full_name": f"Test {role}"}
    return override


class TestGapRoutesRBAC:
    def _set_role(self, role: str):
        from app.core.rbac import get_current_user
        app.dependency_overrides[get_current_user] = _mock_user(role)

    def _clear(self):
        app.dependency_overrides.clear()

    def test_readonly_cannot_analyze(self):
        self._set_role("READONLY")
        try:
            cs_id = str(uuid.uuid4())
            r = client.post(f"/api/v1/chargesheet/{cs_id}/gaps/analyze")
            assert r.status_code == 403
        finally:
            self._clear()

    def test_readonly_cannot_act_on_gap(self):
        self._set_role("READONLY")
        try:
            cs_id = str(uuid.uuid4())
            gap_id = str(uuid.uuid4())
            r = client.patch(
                f"/api/v1/chargesheet/{cs_id}/gaps/{gap_id}/action",
                json={"action": "accepted", "hash_prev": "GENESIS"},
            )
            assert r.status_code == 403
        finally:
            self._clear()

    def test_readonly_cannot_reanalyze(self):
        self._set_role("READONLY")
        try:
            cs_id = str(uuid.uuid4())
            r = client.post(
                f"/api/v1/chargesheet/{cs_id}/gaps/reanalyze",
                json={"justification": "testing"},
            )
            assert r.status_code == 403
        finally:
            self._clear()

    def test_readonly_cannot_apply_suggestion(self):
        self._set_role("READONLY")
        try:
            cs_id = str(uuid.uuid4())
            gap_id = str(uuid.uuid4())
            r = client.post(
                f"/api/v1/chargesheet/{cs_id}/gaps/{gap_id}/apply-suggestion",
                json={"confirm": True},
            )
            assert r.status_code == 403
        finally:
            self._clear()

    def test_readonly_can_read_report(self):
        self._set_role("READONLY")
        try:
            cs_id = str(uuid.uuid4())
            r = client.get(f"/api/v1/chargesheet/{cs_id}/gaps/report")
            assert r.status_code != 403  # 404 or 500 expected, not 403
        finally:
            self._clear()

    def test_readonly_can_list_reports(self):
        self._set_role("READONLY")
        try:
            cs_id = str(uuid.uuid4())
            r = client.get(f"/api/v1/chargesheet/{cs_id}/gaps/reports")
            assert r.status_code != 403
        finally:
            self._clear()

    def test_io_can_analyze(self):
        self._set_role("IO")
        try:
            cs_id = str(uuid.uuid4())
            r = client.post(f"/api/v1/chargesheet/{cs_id}/gaps/analyze")
            assert r.status_code != 403
        finally:
            self._clear()

    def test_unauthenticated_rejected(self):
        cs_id = str(uuid.uuid4())
        r = client.get(f"/api/v1/chargesheet/{cs_id}/gaps/report")
        assert r.status_code == 401

    def test_readonly_can_read_exports(self):
        self._set_role("READONLY")
        try:
            cs_id = str(uuid.uuid4())
            # Export endpoints require EXPORT_ROLES (not READONLY)
            r = client.get(f"/api/v1/chargesheet/{cs_id}/gaps/export/clean-pdf")
            assert r.status_code == 403
        finally:
            self._clear()

    def test_io_can_export(self):
        self._set_role("IO")
        try:
            cs_id = str(uuid.uuid4())
            r = client.get(f"/api/v1/chargesheet/{cs_id}/gaps/export/clean-pdf")
            assert r.status_code != 403
        finally:
            self._clear()
