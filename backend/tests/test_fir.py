"""Tests for the FIR API endpoints.

These tests use an in-memory SQLite-compatible approach via monkeypatching
``app.db.session.get_connection`` so they run without a live PostgreSQL instance
(CI-friendly).  The actual SQL is executed against a real psycopg2 connection
in integration tests.
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core.rbac import get_current_user as _rbac_get_current_user
from app.main import app

# ─────────────────────────────────────────────
# Minimal in-process fake data store
# ─────────────────────────────────────────────

_STORE: Dict[str, Dict[str, Any]] = {}


def _fake_create_fir(conn: Any, fir_data: Dict[str, Any]) -> Dict[str, Any]:
    fir_id = str(uuid.uuid4())
    from datetime import datetime

    # Mirror the CRUD normalisation so tests stay consistent
    primary_sections = fir_data.get("primary_sections")
    if isinstance(primary_sections, str):
        primary_sections = [primary_sections]
    elif not primary_sections:
        primary_sections = []

    record: Dict[str, Any] = {
        "id": fir_id,
        "fir_number": fir_data.get("fir_number"),
        "police_station": fir_data.get("police_station"),
        "district": fir_data.get("district"),
        "fir_date": fir_data.get("fir_date"),
        "occurrence_start": fir_data.get("occurrence_start"),
        "occurrence_end": fir_data.get("occurrence_end"),
        "primary_act": fir_data.get("primary_act"),
        "primary_sections": primary_sections,
        "narrative": fir_data.get("narrative"),
        "raw_text": fir_data.get("raw_text") or fir_data.get("narrative"),
        "source_system": fir_data.get("source_system", "manual"),
        "created_at": datetime.utcnow(),
        "complainants": [],
        "accused": [],
    }
    _STORE[fir_id] = record
    return record


def _fake_get_fir_by_id(conn: Any, fir_id: str, district: Optional[str] = None) -> Optional[Dict[str, Any]]:
    record = _STORE.get(fir_id)
    if record is None:
        return None
    if district is not None and record.get("district") != district:
        return None
    return record


def _fake_list_firs(conn: Any, limit: int = 10, offset: int = 0, district: Optional[str] = None) -> List[Dict[str, Any]]:
    rows = list(_STORE.values())
    if district is not None:
        rows = [r for r in rows if r.get("district") == district]
    return rows[offset:offset + limit]


# ─────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _clear_store():
    """Reset fake store before each test."""
    _STORE.clear()
    yield
    _STORE.clear()


@pytest.fixture()
def client():
    """Return a TestClient with CRUD, session, and RBAC patched."""
    mock_conn = MagicMock()
    # Override RBAC so endpoints don't need a real JWT in tests
    app.dependency_overrides[_rbac_get_current_user] = lambda: {
        "username": "test_admin",
        "role": "ADMIN",
        "district": "Ahmedabad",
        "full_name": "Test Admin",
    }
    with (
        patch("app.api.v1.firs.get_connection", return_value=mock_conn),
        patch("app.api.v1.firs.create_fir", side_effect=_fake_create_fir),
        patch("app.api.v1.firs.get_fir_by_id", side_effect=_fake_get_fir_by_id),
        patch("app.api.v1.firs.list_firs", side_effect=_fake_list_firs),
    ):
        yield TestClient(app)
    app.dependency_overrides.pop(_rbac_get_current_user, None)


# ─────────────────────────────────────────────
# Test fixtures / constants
# ─────────────────────────────────────────────

# Truly minimal: only the required narrative field
MINIMAL_FIR = {
    "narrative": "Complainant reports a theft occurred at their residence.",
}

FULL_FIR = {
    "fir_number": "FIR/2024/002",
    "police_station": "Ahmedabad Central",
    "district": "Ahmedabad",
    "fir_date": "2024-03-15",
    "primary_act": "IPC",
    "primary_sections": ["302", "34"],
    "narrative": "On the night of 15th March, the complainant reported...",
    "raw_text": "ફરિયાદ નંબર 002: ૧૫ માર્ચના રોજ...",
    "source_system": "eGujCop",
    "complainants": [{"name": "Ravi Patel", "age": 35, "address": "123 MG Road"}],
    "accused": [{"name": "Unknown", "age": None, "address": None}],
}


# ─────────────────────────────────────────────
# Create FIR
# ─────────────────────────────────────────────


class TestCreateFIR:
    def test_minimal_fir_only_narrative_returns_201(self, client):
        """A FIR with only a narrative must be accepted (all other fields optional)."""
        response = client.post("/api/v1/firs", json=MINIMAL_FIR)
        assert response.status_code == 201

    def test_minimal_fir_has_uuid(self, client):
        data = client.post("/api/v1/firs", json=MINIMAL_FIR).json()
        assert "id" in data
        uuid.UUID(data["id"])  # raises if not valid UUID

    def test_narrative_stored_correctly(self, client):
        response = client.post("/api/v1/firs", json=MINIMAL_FIR)
        assert response.json()["narrative"] == MINIMAL_FIR["narrative"]

    def test_multilingual_narrative_gujarati_english(self, client):
        """Gujarati + English mixed narrative must round-trip unchanged."""
        narrative = "ફરિયાદ: On the night of 15th March, ચોરી થઈ."
        response = client.post("/api/v1/firs", json={"narrative": narrative})
        assert response.status_code == 201
        assert response.json()["narrative"] == narrative

    def test_primary_sections_as_string_is_auto_converted(self, client):
        """Supplying a bare string for primary_sections should be coerced to a list."""
        payload = {**MINIMAL_FIR, "primary_sections": "302"}
        response = client.post("/api/v1/firs", json=payload)
        assert response.status_code == 201
        assert response.json()["primary_sections"] == ["302"]

    def test_missing_narrative_returns_422(self, client):
        """Omitting narrative must fail with HTTP 422 Unprocessable Entity."""
        response = client.post("/api/v1/firs", json={"fir_number": "FIR/2024/001"})
        assert response.status_code == 422

    def test_blank_narrative_returns_422(self, client):
        """A whitespace-only narrative must fail validation."""
        response = client.post("/api/v1/firs", json={"narrative": "   "})
        assert response.status_code == 422

    def test_create_full_fir(self, client):
        response = client.post("/api/v1/firs", json=FULL_FIR)
        assert response.status_code == 201
        data = response.json()
        assert data["fir_number"] == FULL_FIR["fir_number"]
        assert data["primary_sections"] == ["302", "34"]


# ─────────────────────────────────────────────
# Retrieve FIR
# ─────────────────────────────────────────────


class TestRetrieveFIR:
    def test_get_fir_by_id(self, client):
        created = client.post("/api/v1/firs", json=MINIMAL_FIR).json()
        response = client.get(f"/api/v1/firs/{created['id']}")
        assert response.status_code == 200
        assert response.json()["id"] == created["id"]

    def test_get_fir_narrative_intact(self, client):
        payload = {"narrative": "Important narrative."}
        created = client.post("/api/v1/firs", json=payload).json()
        fetched = client.get(f"/api/v1/firs/{created['id']}").json()
        assert fetched["narrative"] == "Important narrative."

    def test_get_nonexistent_fir_returns_404(self, client):
        response = client.get(f"/api/v1/firs/{uuid.uuid4()}")
        assert response.status_code == 404


# ─────────────────────────────────────────────
# List FIRs
# ─────────────────────────────────────────────


class TestListFIRs:
    def test_list_empty(self, client):
        response = client.get("/api/v1/firs")
        assert response.status_code == 200
        assert response.json() == []

    def test_list_returns_created_firs(self, client):
        client.post("/api/v1/firs", json=MINIMAL_FIR)
        client.post("/api/v1/firs", json={**MINIMAL_FIR, "fir_number": "FIR/2024/003"})
        response = client.get("/api/v1/firs")
        assert len(response.json()) == 2
