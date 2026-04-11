from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_login_success():
    resp = client.post("/api/v1/auth/login", json={
        "username": "admin", "password": "atlas2025"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


def test_login_wrong_password():
    resp = client.post("/api/v1/auth/login", json={
        "username": "admin", "password": "wrong"
    })
    assert resp.status_code == 401


def test_login_unknown_user():
    resp = client.post("/api/v1/auth/login", json={
        "username": "nobody", "password": "atlas2025"
    })
    assert resp.status_code == 401


def test_me_without_token():
    resp = client.get("/api/v1/auth/me")
    assert resp.status_code == 401


def test_me_with_valid_token():
    login_resp = client.post("/api/v1/auth/login", json={
        "username": "admin", "password": "atlas2025"
    })
    token = login_resp.json()["access_token"]
    resp = client.get("/api/v1/auth/me", headers={
        "Authorization": f"Bearer {token}"
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["username"] == "admin"
    assert data["role"] == "ADMIN"


def test_chargesheet_health():
    resp = client.get("/api/v1/chargesheet/health")
    assert resp.status_code == 200
    assert resp.json()["module"] == "chargesheet"


def test_sop_health():
    resp = client.get("/api/v1/sop/health")
    assert resp.status_code == 200
    assert resp.json()["module"] == "sop"


def test_dashboard_health():
    resp = client.get("/api/v1/dashboard/health")
    assert resp.status_code == 200
    assert resp.json()["module"] == "dashboard"


def test_dashboard_stats():
    resp = client.get("/api/v1/dashboard/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert "total_firs" in data
    assert "districts" in data
