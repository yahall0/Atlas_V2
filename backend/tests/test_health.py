from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health():
    response = client.get("/api/v1/health")
    data = response.json()

    assert response.status_code == 200
    assert data["status"] == "healthy"
    assert "model_version" in data
