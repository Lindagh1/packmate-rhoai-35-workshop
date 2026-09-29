from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_ready_endpoint() -> None:
    response = client.get("/ready")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert "version" in body


def test_metrics_endpoint_exposes_packmate_series() -> None:
    client.get("/health")
    response = client.get("/metrics")
    assert response.status_code == 200
    text = response.text
    assert "packmate_http_requests_total" in text
    assert "packmate_http_request_duration_seconds" in text


def test_health_still_ok() -> None:
    assert client.get("/health").json() == {"status": "ok"}
