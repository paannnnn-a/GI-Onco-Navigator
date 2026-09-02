from fastapi.testclient import TestClient

from backend.app import main
from backend.app.observability import Metrics
from backend.app.storage import Database


def test_health_metrics_and_security_headers(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(main, "database", Database(tmp_path / "health.db"))
    monkeypatch.setattr(main, "metrics", Metrics())
    client = TestClient(main.app)
    response = client.get("/health/ready", headers={"X-Request-ID": "test-request"})
    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "test-request"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["Cache-Control"] == "no-store"
    metrics = client.get("/metrics").text
    assert 'route="/health/ready",status="200"' in metrics
