import json
import os

import httpx
from fastapi.testclient import TestClient

os.environ["RESERVATIONS_URL"] = "http://reservations"
os.environ["INVENTORY_URL"] = "http://inventory"

from app.main import app, get_http_client  # noqa: E402


def make_client(handler):
    async def override_http_client():
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler)
        ) as client:
            yield client

    app.dependency_overrides[get_http_client] = override_http_client
    return TestClient(app)


def test_health():
    response = TestClient(app).get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_create_reservation_preserves_status_and_body():
    def handler(request):
        assert request.method == "POST"
        assert request.url == httpx.URL("http://reservations/reservations")
        assert json.loads(request.content) == {
            "event_id": 1,
            "email": "person@example.com",
            "amount": 49.99,
        }
        return httpx.Response(
            201,
            json={"id": "reservation-123", "status": "confirmed"},
        )

    client = make_client(handler)
    response = client.post(
        "/api/reservations",
        json={
            "event_id": 1,
            "email": "person@example.com",
            "amount": 49.99,
        },
    )

    assert response.status_code == 201
    assert response.json() == {
        "id": "reservation-123",
        "status": "confirmed",
    }


def test_get_reservation_preserves_upstream_error():
    def handler(request):
        assert request.url == httpx.URL(
            "http://reservations/reservations/missing"
        )
        return httpx.Response(404, json={"detail": "Reservation not found"})

    client = make_client(handler)
    response = client.get("/api/reservations/missing")

    assert response.status_code == 404
    assert response.json() == {"detail": "Reservation not found"}


def test_get_inventory():
    def handler(request):
        assert request.url == httpx.URL("http://inventory/inventory/1")
        return httpx.Response(
            200,
            json={
                "event_id": 1,
                "event_name": "Concierto de prueba",
                "available_seats": 10,
            },
        )

    client = make_client(handler)
    response = client.get("/api/inventory/1")

    assert response.status_code == 200
    assert response.json()["available_seats"] == 10


def test_upstream_service_unavailable():
    def handler(request):
        raise httpx.ConnectError("unavailable", request=request)

    client = make_client(handler)
    response = client.get("/api/inventory/1")

    assert response.status_code == 503
    assert response.json() == {"detail": "Upstream service unavailable"}
