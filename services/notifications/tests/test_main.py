from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_successful_notification(monkeypatch):
    monkeypatch.setenv("NOTIFICATION_DELAY_SECONDS", "0")
    monkeypatch.setenv("NOTIFICATION_FAILURE_RATE", "0")

    response = client.post(
        "/notifications",
        json={
            "reservation_id": "reservation-123",
            "email": "person@example.com",
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "status": "sent",
        "reservation_id": "reservation-123",
    }


def test_simulated_failure(monkeypatch):
    monkeypatch.setenv("NOTIFICATION_DELAY_SECONDS", "0")
    monkeypatch.setenv("NOTIFICATION_FAILURE_RATE", "1")

    response = client.post(
        "/notifications",
        json={
            "reservation_id": "reservation-456",
            "email": "person@example.com",
        },
    )

    assert response.status_code == 503
