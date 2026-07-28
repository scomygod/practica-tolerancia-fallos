import logging
import os
from collections.abc import AsyncGenerator
from decimal import Decimal
from uuid import UUID, uuid4

import httpx
from fastapi import Depends, FastAPI, HTTPException, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database import Reservation, get_db
from app.resilience import (
    CircuitBreaker,
    CircuitOpenError,
    InventoryConflictError,
    InventoryUnavailableError,
    PaymentUnavailableError,
    process_payment,
    release_inventory,
    reserve_inventory,
    send_notification,
)
from app.schemas import ReservationCreate, ReservationResponse

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

INVENTORY_URL = os.environ["INVENTORY_URL"].rstrip("/")
PAYMENTS_URL = os.environ["PAYMENTS_URL"].rstrip("/")
NOTIFICATIONS_URL = os.environ["NOTIFICATIONS_URL"].rstrip("/")

INVENTORY_TIMEOUT_SECONDS = float(
    os.getenv("INVENTORY_TIMEOUT_SECONDS", "3")
)
PAYMENT_TIMEOUT_SECONDS = float(os.getenv("PAYMENT_TIMEOUT_SECONDS", "3"))
NOTIFICATION_TIMEOUT_SECONDS = float(
    os.getenv("NOTIFICATION_TIMEOUT_SECONDS", "2")
)
INVENTORY_MAX_RETRIES = int(os.getenv("INVENTORY_MAX_RETRIES", "3"))

PAYMENT_CIRCUIT_BREAKER = CircuitBreaker(
    failure_threshold=int(
        os.getenv("CIRCUIT_BREAKER_FAILURE_THRESHOLD", "3")
    ),
    recovery_seconds=float(
        os.getenv("CIRCUIT_BREAKER_RECOVERY_SECONDS", "20")
    ),
)

app = FastAPI(title="Reservations Service")


async def get_http_client() -> AsyncGenerator[httpx.AsyncClient, None]:
    async with httpx.AsyncClient() as client:
        yield client


def save_reservation(database: Session, reservation: Reservation) -> None:
    try:
        database.add(reservation)
        database.commit()
    except SQLAlchemyError as error:
        database.rollback()
        logger.exception("No se pudo guardar la reserva")
        raise HTTPException(
            status_code=503,
            detail="Database unavailable",
        ) from error


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "healthy"}


@app.post(
    "/reservations",
    response_model=ReservationResponse,
    response_model_exclude_none=True,
    status_code=status.HTTP_201_CREATED,
)
async def create_reservation(
    request: ReservationCreate,
    database: Session = Depends(get_db),
    client: httpx.AsyncClient = Depends(get_http_client),
) -> ReservationResponse:
    reservation_id = uuid4()
    logger.info("Iniciando reserva %s", reservation_id)

    try:
        await reserve_inventory(
            client=client,
            inventory_url=INVENTORY_URL,
            event_id=request.event_id,
            timeout_seconds=INVENTORY_TIMEOUT_SECONDS,
            max_attempts=INVENTORY_MAX_RETRIES,
        )
    except InventoryConflictError as error:
        raise HTTPException(
            status_code=409,
            detail="No seats available",
        ) from error
    except InventoryUnavailableError as error:
        logger.warning("Inventario no disponible para reserva %s", reservation_id)
        raise HTTPException(
            status_code=503,
            detail="Inventory service unavailable after retries",
        ) from error

    try:
        await process_payment(
            client=client,
            payments_url=PAYMENTS_URL,
            reservation_id=str(reservation_id),
            amount=request.amount,
            timeout_seconds=PAYMENT_TIMEOUT_SECONDS,
            circuit_breaker=PAYMENT_CIRCUIT_BREAKER,
        )
    except (PaymentUnavailableError, CircuitOpenError) as error:
        compensation_succeeded = await release_inventory(
            client=client,
            inventory_url=INVENTORY_URL,
            event_id=request.event_id,
            timeout_seconds=INVENTORY_TIMEOUT_SECONDS,
        )
        if compensation_succeeded:
            logger.info(
                "Compensación completada para reserva %s",
                reservation_id,
            )
        else:
            logger.error(
                "Compensación fallida para reserva %s",
                reservation_id,
            )

        failed_reservation = Reservation(
            id=reservation_id,
            event_id=request.event_id,
            email=request.email,
            amount=Decimal(str(request.amount)),
            status="payment_failed",
            notification_status="not_sent",
        )
        save_reservation(database, failed_reservation)
        logger.warning("Pago fallido para reserva %s", reservation_id)
        detail = (
            "Payment circuit breaker is open"
            if isinstance(error, CircuitOpenError)
            else "Payment service unavailable"
        )
        raise HTTPException(status_code=503, detail=detail) from error

    notification_sent = await send_notification(
        client=client,
        notifications_url=NOTIFICATIONS_URL,
        reservation_id=str(reservation_id),
        email=request.email,
        timeout_seconds=NOTIFICATION_TIMEOUT_SECONDS,
    )
    notification_status = "sent" if notification_sent else "pending"

    reservation = Reservation(
        id=reservation_id,
        event_id=request.event_id,
        email=request.email,
        amount=Decimal(str(request.amount)),
        status="confirmed",
        notification_status=notification_status,
    )
    save_reservation(database, reservation)

    message = (
        "Reservation confirmed"
        if notification_sent
        else "Reservation confirmed; notification pending"
    )
    logger.info(
        "Reserva %s confirmada con notificación %s",
        reservation_id,
        notification_status,
    )
    return ReservationResponse(
        id=reservation_id,
        event_id=request.event_id,
        email=request.email,
        amount=request.amount,
        status="confirmed",
        notification_status=notification_status,
        message=message,
    )


@app.get(
    "/reservations/{reservation_id}",
    response_model=ReservationResponse,
    response_model_exclude_none=True,
)
def get_reservation(
    reservation_id: UUID,
    database: Session = Depends(get_db),
) -> Reservation:
    try:
        reservation = database.get(Reservation, reservation_id)
    except SQLAlchemyError as error:
        logger.exception("No se pudo consultar la reserva %s", reservation_id)
        raise HTTPException(
            status_code=503,
            detail="Database unavailable",
        ) from error

    if reservation is None:
        raise HTTPException(status_code=404, detail="Reservation not found")

    return reservation
