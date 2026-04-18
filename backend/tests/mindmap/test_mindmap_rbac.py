"""Tests for mindmap RBAC — T53-M8.

Verifies role-based access control on mindmap endpoints.
"""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _mock_token(role: str, district: str = "Ahmedabad"):
    """Create a mock auth header for a given role."""
    return {
        "sub": f"test_{role.lower()}",
        "role": role,
        "district": district,
        "full_name": f"Test {role}",
        "type": "access",
    }


class TestMindmapRBAC:
    """Test RBAC enforcement on mindmap endpoints."""

    @pytest.fixture
    def mock_conn(self):
        """Mock the database connection."""
        conn = MagicMock()
        with patch("app.db.session.get_connection", return_value=conn):
            yield conn

    def _auth_header(self, token_payload: dict):
        """Create a patched auth dependency."""
        async def override_get_current_user():
            return {
                "username": token_payload["sub"],
                "role": token_payload["role"],
                "district": token_payload["district"],
                "full_name": token_payload["full_name"],
            }
        return override_get_current_user

    def test_readonly_cannot_generate(self):
        """READONLY role should not be able to generate mindmap."""
        from app.core.rbac import get_current_user
        token = _mock_token("READONLY")

        app.dependency_overrides[get_current_user] = self._auth_header(token)
        try:
            fir_id = str(uuid.uuid4())
            resp = client.post(f"/api/v1/fir/{fir_id}/mindmap")
            assert resp.status_code == 403
        finally:
            app.dependency_overrides.clear()

    def test_readonly_cannot_update_status(self):
        """READONLY role should not be able to update node status."""
        from app.core.rbac import get_current_user
        token = _mock_token("READONLY")

        app.dependency_overrides[get_current_user] = self._auth_header(token)
        try:
            fir_id = str(uuid.uuid4())
            node_id = str(uuid.uuid4())
            resp = client.patch(
                f"/api/v1/fir/{fir_id}/mindmap/nodes/{node_id}/status",
                json={"status": "addressed", "hash_prev": "GENESIS"},
            )
            assert resp.status_code == 403
        finally:
            app.dependency_overrides.clear()

    def test_readonly_cannot_add_custom_node(self):
        """READONLY role should not be able to add custom nodes."""
        from app.core.rbac import get_current_user
        token = _mock_token("READONLY")

        app.dependency_overrides[get_current_user] = self._auth_header(token)
        try:
            fir_id = str(uuid.uuid4())
            resp = client.post(
                f"/api/v1/fir/{fir_id}/mindmap/nodes",
                json={"title": "Custom Node", "description_md": "test"},
            )
            assert resp.status_code == 403
        finally:
            app.dependency_overrides.clear()

    def test_readonly_cannot_regenerate(self):
        """READONLY role should not be able to regenerate mindmap."""
        from app.core.rbac import get_current_user
        token = _mock_token("READONLY")

        app.dependency_overrides[get_current_user] = self._auth_header(token)
        try:
            fir_id = str(uuid.uuid4())
            resp = client.post(
                f"/api/v1/fir/{fir_id}/mindmap/regenerate",
                json={"justification": "testing"},
            )
            assert resp.status_code == 403
        finally:
            app.dependency_overrides.clear()

    def test_io_can_access_write_endpoints(self):
        """IO role should have access to write endpoints (will fail on
        DB but should not fail on auth)."""
        from app.core.rbac import get_current_user
        token = _mock_token("IO")

        app.dependency_overrides[get_current_user] = self._auth_header(token)
        try:
            fir_id = str(uuid.uuid4())
            # These will fail with 500 (no DB) or 404 (no FIR), NOT 403
            resp = client.post(f"/api/v1/fir/{fir_id}/mindmap")
            assert resp.status_code != 403

            resp = client.post(
                f"/api/v1/fir/{fir_id}/mindmap/regenerate",
                json={"justification": "testing regeneration"},
            )
            assert resp.status_code != 403
        finally:
            app.dependency_overrides.clear()

    def test_unauthenticated_rejected(self):
        """Requests without auth should be rejected."""
        fir_id = str(uuid.uuid4())
        resp = client.get(f"/api/v1/fir/{fir_id}/mindmap")
        assert resp.status_code == 401

    def test_readonly_can_read_mindmap(self):
        """READONLY role should be able to read mindmap (will fail on DB,
        not auth)."""
        from app.core.rbac import get_current_user
        token = _mock_token("READONLY")

        app.dependency_overrides[get_current_user] = self._auth_header(token)
        try:
            fir_id = str(uuid.uuid4())
            resp = client.get(f"/api/v1/fir/{fir_id}/mindmap")
            # Should fail with 404 or 500 (no DB), not 403
            assert resp.status_code != 403
        finally:
            app.dependency_overrides.clear()

    def test_readonly_can_read_versions(self):
        """READONLY can list versions."""
        from app.core.rbac import get_current_user
        token = _mock_token("READONLY")

        app.dependency_overrides[get_current_user] = self._auth_header(token)
        try:
            fir_id = str(uuid.uuid4())
            resp = client.get(f"/api/v1/fir/{fir_id}/mindmap/versions")
            assert resp.status_code != 403
        finally:
            app.dependency_overrides.clear()

    def test_readonly_can_export_pdf(self):
        """READONLY can export PDF."""
        from app.core.rbac import get_current_user
        token = _mock_token("READONLY")

        app.dependency_overrides[get_current_user] = self._auth_header(token)
        try:
            fir_id = str(uuid.uuid4())
            resp = client.get(f"/api/v1/fir/{fir_id}/mindmap/export/pdf")
            assert resp.status_code != 403
        finally:
            app.dependency_overrides.clear()
