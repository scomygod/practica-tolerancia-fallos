from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health(monkeypatch):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_successful_payment(monkeypatch):
    monkeypatch.setenv("PAYMENT_DELAY_SECONDS", "0")
    monkeypatch.setenv("PAYMENT_FAILURE_RATE", "0")

    response = client.post(
        "/payments",
        json={"reservation_id": "reservation-123", "amount": 49.99},
    )

    body = response.json()
    assert response.status_code == 200
    assert body["status"] == "approved"
    assert body["reservation_id"] == "reservation-123"
    assert body["transaction_id"]


def test_simulated_failure(monkeypatch):
    monkeypatch.setenv("PAYMENT_DELAY_SECONDS", "0")
    monkeypatch.setenv("PAYMENT_FAILURE_RATE", "1")

    response = client.post(
        "/payments",
        json={"reservation_id": "reservation-456", "amount": 20.0},
    )

    assert response.status_code == 503
