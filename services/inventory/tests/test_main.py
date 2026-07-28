import os
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

os.environ["DATABASE_URL"] = "postgresql+psycopg://test:test@localhost/test"

from app.main import app, get_db  # noqa: E402

client = TestClient(app)


@pytest.fixture
def database():
    session = MagicMock(spec=Session)
    app.dependency_overrides[get_db] = lambda: session
    yield session
    app.dependency_overrides.clear()


def test_health():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_get_inventory(database):
    result = database.execute.return_value
    result.mappings.return_value.first.return_value = {
        "event_id": 1,
        "event_name": "Concierto de prueba",
        "available_seats": 10,
    }

    response = client.get("/inventory/1")

    assert response.status_code == 200
    assert response.json()["available_seats"] == 10


def test_get_inventory_not_found(database):
    database.execute.return_value.mappings.return_value.first.return_value = None

    response = client.get("/inventory/99")

    assert response.status_code == 404


def test_reserve_is_single_atomic_update(database):
    database.execute.return_value.scalar_one_or_none.return_value = 9

    response = client.post("/inventory/1/reserve")

    statement = database.execute.call_args.args[0]
    sql = str(statement.compile(dialect=postgresql.dialect())).upper()

    assert response.status_code == 200
    assert response.json() == {"event_id": 1, "available_seats": 9}
    assert sql.startswith("UPDATE INVENTORY")
    assert "AVAILABLE_SEATS >" in sql
    assert "AVAILABLE_SEATS - " in sql
    assert "RETURNING INVENTORY.AVAILABLE_SEATS" in sql
    assert database.execute.call_count == 1
    database.commit.assert_called_once()


def test_reserve_without_availability(database):
    database.execute.return_value.scalar_one_or_none.return_value = None

    response = client.post("/inventory/1/reserve")

    assert response.status_code == 409
    database.rollback.assert_called_once()
    database.commit.assert_not_called()


def test_release_is_single_update(database):
    database.execute.return_value.scalar_one_or_none.return_value = 10

    response = client.post("/inventory/1/release")

    statement = database.execute.call_args.args[0]
    sql = str(statement.compile(dialect=postgresql.dialect())).upper()

    assert response.status_code == 200
    assert response.json() == {"event_id": 1, "available_seats": 10}
    assert sql.startswith("UPDATE INVENTORY")
    assert "AVAILABLE_SEATS + " in sql
    assert "RETURNING INVENTORY.AVAILABLE_SEATS" in sql
    assert database.execute.call_count == 1
    database.commit.assert_called_once()


def test_release_unknown_event(database):
    database.execute.return_value.scalar_one_or_none.return_value = None

    response = client.post("/inventory/99/release")

    assert response.status_code == 404
    database.rollback.assert_called_once()
    database.commit.assert_not_called()


def test_reset_inventory(database):
    database.execute.return_value.rowcount = 1

    response = client.post(
        "/inventory/1/reset",
        json={"available_seats": 10},
    )

    assert response.status_code == 200
    assert response.json() == {"event_id": 1, "available_seats": 10}
    database.commit.assert_called_once()


def test_reset_rejects_negative_seats(database):
    response = client.post(
        "/inventory/1/reset",
        json={"available_seats": -1},
    )

    assert response.status_code == 422
    database.execute.assert_not_called()


def test_database_error_returns_503(database):
    database.execute.side_effect = OperationalError(
        "statement",
        {},
        Exception("connection failed"),
    )

    response = client.get("/inventory/1")

    assert response.status_code == 503
    database.rollback.assert_called_once()
