"""Tests for GET /dashboard/stats — live stats endpoint."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch

from app.main import app
from app.core.rbac import Role


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def client():
    return TestClient(app)


def _make_token(role: str, district: str = "Ahmedabad"):
    from app.core.security import create_access_token

    return create_access_token(
        {
            "sub": f"test_{role.lower()}",
            "role": role,
            "district": district,
            "full_name": f"Test {role}",
        }
    )


@pytest.fixture
def sp_headers():
    return {"Authorization": f"Bearer {_make_token(Role.SP.value, 'Ahmedabad')}"}


@pytest.fixture
def io_headers():
    return {"Authorization": f"Bearer {_make_token(Role.IO.value, 'Surat')}"}


def _mock_cursor(rows: list[tuple]):
    """Return a mock cursor that yields *rows* on successive fetchone() calls."""
    cursor = MagicMock()
    cursor.fetchone.side_effect = rows
    cursor.__enter__ = lambda s: s
    cursor.__exit__ = MagicMock(return_value=False)
    return cursor


def _mock_conn(rows: list[tuple]):
    conn = MagicMock()
    conn.cursor.return_value = _mock_cursor(rows)
    return conn


# ---------------------------------------------------------------------------
# Stats endpoint — unauthenticated
# ---------------------------------------------------------------------------


def test_dashboard_stats_requires_auth(client):
    resp = client.get("/api/v1/dashboard/stats")
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Stats endpoint — authenticated
# ---------------------------------------------------------------------------


@patch("app.api.v1.dashboard.get_connection")
def test_dashboard_stats_schema(mock_get_conn, client, sp_headers):
    mock_get_conn.return_value = _mock_conn(
        [(100,), (15,), (6,), (72.5,), (5,)]
    )
    resp = client.get("/api/v1/dashboard/stats", headers=sp_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "total_firs" in data
    assert "pending_review" in data
    assert "districts" in data
    assert "completeness_avg" in data
    assert "ingested_today" in data


@patch("app.api.v1.dashboard.get_connection")
def test_dashboard_stats_values(mock_get_conn, client, sp_headers):
    mock_get_conn.return_value = _mock_conn(
        [(100,), (15,), (6,), (72.5,), (5,)]
    )
    resp = client.get("/api/v1/dashboard/stats", headers=sp_headers)
    data = resp.json()
    assert data["total_firs"] == 100
    assert data["pending_review"] == 15
    assert data["districts"] == 6
    assert data["completeness_avg"] == 72.5
    assert data["ingested_today"] == 5


@patch("app.api.v1.dashboard.get_connection")
def test_dashboard_stats_zero_db(mock_get_conn, client, sp_headers):
    """Empty database returns all zeros without error."""
    mock_get_conn.return_value = _mock_conn(
        [(0,), (0,), (0,), (0.0,), (0,)]
    )
    resp = client.get("/api/v1/dashboard/stats", headers=sp_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_firs"] == 0
