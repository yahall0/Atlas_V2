"""Tests for POST /predict/classify and GET /predict/model-info endpoints."""

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
def auth_headers():
    """Return an Authorization header for a mock SHO user."""
    import os
    from app.core.security import create_access_token

    token = create_access_token(
        {
            "sub": "test_sho",
            "role": Role.SHO.value,
            "district": "Ahmedabad",
            "full_name": "Test SHO",
        }
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def io_headers():
    from app.core.security import create_access_token

    token = create_access_token(
        {
            "sub": "test_io",
            "role": Role.IO.value,
            "district": "Ahmedabad",
            "full_name": "Test IO",
        }
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def client():
    return TestClient(app)


# ---------------------------------------------------------------------------
# POST /predict/classify
# ---------------------------------------------------------------------------


def test_classify_returns_200(client, auth_headers):
    resp = client.post(
        "/api/v1/predict/classify",
        json={"text": "The accused stole gold ornaments and cash."},
        headers=auth_headers,
    )
    assert resp.status_code == 200


def test_classify_response_schema(client, auth_headers):
    resp = client.post(
        "/api/v1/predict/classify",
        json={"text": "The accused committed murder. Section 302."},
        headers=auth_headers,
    )
    data = resp.json()
    assert "category" in data
    assert "confidence" in data
    assert "method" in data
    assert "detected_lang" in data
    assert "persisted" in data
    assert data["persisted"] is False  # no fir_id supplied


def test_classify_category_in_atlas_categories(client, auth_headers):
    from app.nlp.classify import ATLAS_CATEGORIES

    resp = client.post(
        "/api/v1/predict/classify",
        json={"text": "Narcotics drug NDPS case."},
        headers=auth_headers,
    )
    data = resp.json()
    assert data["category"] in ATLAS_CATEGORIES


def test_classify_confidence_is_float(client, auth_headers):
    resp = client.post(
        "/api/v1/predict/classify",
        json={"text": "Fraud and cheating by accused."},
        headers=auth_headers,
    )
    data = resp.json()
    assert isinstance(data["confidence"], float)
    assert 0.0 <= data["confidence"] <= 1.0


def test_classify_requires_auth(client):
    resp = client.post(
        "/api/v1/predict/classify",
        json={"text": "some text"},
    )
    assert resp.status_code == 403


def test_classify_empty_text_rejected(client, auth_headers):
    resp = client.post(
        "/api/v1/predict/classify",
        json={"text": ""},
        headers=auth_headers,
    )
    # Pydantic min_length=1 should reject empty text
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /predict/model-info
# ---------------------------------------------------------------------------


def test_model_info_returns_200(client, auth_headers):
    resp = client.get("/api/v1/predict/model-info", headers=auth_headers)
    assert resp.status_code == 200


def test_model_info_schema(client, auth_headers):
    resp = client.get("/api/v1/predict/model-info", headers=auth_headers)
    data = resp.json()
    assert "model_variant" in data
    assert "categories" in data
    assert "status" in data
    assert isinstance(data["categories"], list)


def test_model_info_requires_auth(client):
    resp = client.get("/api/v1/predict/model-info")
    assert resp.status_code == 403
