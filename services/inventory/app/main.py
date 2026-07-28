import logging
import os
from collections.abc import Generator

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import (
    CheckConstraint,
    Column,
    Integer,
    MetaData,
    String,
    Table,
    create_engine,
    select,
    update,
)
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DATABASE_URL = os.environ["DATABASE_URL"]

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine)

metadata = MetaData()
inventory = Table(
    "inventory",
    metadata,
    Column("event_id", Integer, primary_key=True),
    Column("event_name", String(120), nullable=False),
    Column("available_seats", Integer, nullable=False),
    CheckConstraint("available_seats >= 0"),
)

app = FastAPI(title="Inventory Service")


class InventoryResponse(BaseModel):
    event_id: int
    event_name: str
    available_seats: int


class SeatsRequest(BaseModel):
    available_seats: int = Field(ge=0)


class SeatsResponse(BaseModel):
    event_id: int
    available_seats: int


def get_db() -> Generator[Session, None, None]:
    database = SessionLocal()
    try:
        yield database
    finally:
        database.close()


def handle_database_error(database: Session, error: SQLAlchemyError) -> None:
    database.rollback()
    logger.exception("Error de base de datos", exc_info=error)
    raise HTTPException(status_code=503, detail="Database unavailable") from error


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "healthy"}


@app.get("/inventory/{event_id}", response_model=InventoryResponse)
def get_inventory(
    event_id: int,
    database: Session = Depends(get_db),
) -> InventoryResponse:
    statement = select(inventory).where(inventory.c.event_id == event_id)

    try:
        row = database.execute(statement).mappings().first()
    except SQLAlchemyError as error:
        handle_database_error(database, error)

    if row is None:
        raise HTTPException(status_code=404, detail="Event not found")

    return InventoryResponse(**row)


@app.post("/inventory/{event_id}/reserve", response_model=SeatsResponse)
def reserve_seat(
    event_id: int,
    database: Session = Depends(get_db),
) -> SeatsResponse:
    statement = (
        update(inventory)
        .where(
            inventory.c.event_id == event_id,
            inventory.c.available_seats > 0,
        )
        .values(available_seats=inventory.c.available_seats - 1)
        .returning(inventory.c.available_seats)
    )

    try:
        available_seats = database.execute(statement).scalar_one_or_none()
        if available_seats is None:
            database.rollback()
            raise HTTPException(status_code=409, detail="No seats available")
        database.commit()
    except SQLAlchemyError as error:
        handle_database_error(database, error)

    logger.info(
        "Asiento reservado para evento %s; quedan %s",
        event_id,
        available_seats,
    )
    return SeatsResponse(event_id=event_id, available_seats=available_seats)


@app.post("/inventory/{event_id}/reset", response_model=SeatsResponse)
def reset_inventory(
    event_id: int,
    request: SeatsRequest,
    database: Session = Depends(get_db),
) -> SeatsResponse:
    statement = (
        update(inventory)
        .where(inventory.c.event_id == event_id)
        .values(available_seats=request.available_seats)
    )

    try:
        result = database.execute(statement)
        if result.rowcount == 0:
            database.rollback()
            raise HTTPException(status_code=404, detail="Event not found")
        database.commit()
    except SQLAlchemyError as error:
        handle_database_error(database, error)

    logger.info(
        "Inventario del evento %s reiniciado a %s asientos",
        event_id,
        request.available_seats,
    )
    return SeatsResponse(
        event_id=event_id,
        available_seats=request.available_seats,
    )
