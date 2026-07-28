import os
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient

os.environ["DATABASE_URL"] = "postgresql+psycopg://test:test@localhost/test"
os.environ["INVENTORY_URL"] = "http://inventory"
os.environ["PAYMENTS_URL"] = "http://payments"
os.environ["NOTIFICATIONS_URL"] = "http://notifications"

from app.database import get_db  # noqa: E402
from app.main import (  # noqa: E402
    PAYMENT_CIRCUIT_BREAKER,
    app,
    get_http_client,
)


class FakeDatabase:
    def __init__(self):
        self.records = []

    def add(self, reservation):
        self.records.append(reservation)

    def commit(self):
        pass

    def rollback(self):
        pass

    def get(self, model, reservation_id):
        return next(
            (
                record
                for record in self.records
                if record.id == reservation_id
            ),
            None,
        )


@pytest.fixture(autouse=True)
def reset_circuit_breaker():
    PAYMENT_CIRCUIT_BREAKER.reset()
    yield
    PAYMENT_CIRCUIT_BREAKER.reset()


def make_client(handler):
    database = FakeDatabase()

    def override_database():
        yield database

    async def override_http_client():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler)
        ) as client:
            yield client

    app.dependency_overrides[get_db] = override_database
    app.dependency_overrides[get_http_client] = override_http_client
    return TestClient(app), database


def reservation_payload():
    return {
        "event_id": 1,
        "email": "person@example.com",
        "amount": 49.99,
    }


def test_successful_reservation():
    def handler(request):
        return httpx.Response(200, json={"status": "ok"})

    client, database = make_client(handler)
    response = client.post("/reservations", json=reservation_payload())

    assert response.status_code == 201
    assert response.json()["status"] == "confirmed"
    assert response.json()["notification_status"] == "sent"
    assert database.records[0].status == "confirmed"


def test_inventory_without_availability():
    requested_hosts = []

    def handler(request):
        requested_hosts.append(request.url.host)
        return httpx.Response(409)

    client, database = make_client(handler)
    response = client.post("/reservations", json=reservation_payload())

    assert response.status_code == 409
    assert requested_hosts == ["inventory"]
    assert database.records == []


def test_inventory_unavailable_retries_three_times():
    attempts = 0

    def handler(request):
        nonlocal attempts
        attempts += 1
        raise httpx.ConnectError("unavailable", request=request)

    client, database = make_client(handler)
    with patch("app.resilience.asyncio.sleep", new=AsyncMock()):
        response = client.post("/reservations", json=reservation_payload())

    assert response.status_code == 503
    assert response.json()["detail"] == (
        "Inventory service unavailable after retries"
    )
    assert attempts == 3
    assert database.records == []


def test_payment_timeout_records_failure():
    release_calls = 0

    def handler(request):
        nonlocal release_calls
        if request.url.host == "inventory":
            if request.url.path.endswith("/release"):
                release_calls += 1
            return httpx.Response(200)
        if request.url.host == "payments":
            raise httpx.ReadTimeout("timeout", request=request)
        raise AssertionError("Notifications must not be called")

    client, database = make_client(handler)
    response = client.post("/reservations", json=reservation_payload())

    assert response.status_code == 503
    assert database.records[0].status == "payment_failed"
    assert database.records[0].notification_status == "not_sent"
    assert release_calls == 1


def test_circuit_breaker_opens_after_three_failures():
    payment_calls = 0

    def handler(request):
        nonlocal payment_calls
        if request.url.host == "inventory":
            return httpx.Response(200)
        if request.url.host == "payments":
            payment_calls += 1
            return httpx.Response(503)
        raise AssertionError("Notifications must not be called")

    client, database = make_client(handler)

    for _ in range(3):
        assert client.post(
            "/reservations",
            json=reservation_payload(),
        ).status_code == 503

    open_response = client.post("/reservations", json=reservation_payload())

    assert open_response.status_code == 503
    assert open_response.json()["detail"] == (
        "Payment circuit breaker is open"
    )
    assert payment_calls == 3
    assert len(database.records) == 4


def test_notification_fallback_keeps_reservation_confirmed():
    def handler(request):
        if request.url.host == "notifications":
            return httpx.Response(503)
        return httpx.Response(200)

    client, database = make_client(handler)
    response = client.post("/reservations", json=reservation_payload())

    assert response.status_code == 201
    assert response.json()["status"] == "confirmed"
    assert response.json()["notification_status"] == "pending"
    assert "notification pending" in response.json()["message"]
    assert database.records[0].status == "confirmed"
    assert database.records[0].notification_status == "pending"


def test_failed_compensation_is_logged_once(caplog):
    release_calls = 0

    def handler(request):
        nonlocal release_calls
        if request.url.host == "payments":
            return httpx.Response(503)
        if request.url.path.endswith("/release"):
            release_calls += 1
            return httpx.Response(503)
        return httpx.Response(200)

    client, database = make_client(handler)
    with caplog.at_level("ERROR"):
        response = client.post("/reservations", json=reservation_payload())

    assert response.status_code == 503
    assert release_calls == 1
    assert "Compensación fallida" in caplog.text
    assert database.records[0].status == "payment_failed"
