import pytest


@pytest.mark.django_db
def test_health_endpoint_returns_healthy_status(client):
    response = client.get("/api/v1/health/")

    assert response.status_code == 200

    data = response.json()

    assert data["status"] == "healthy"
    assert data["service"] == "fuel-route-optimizer"
    assert "timestamp" in data