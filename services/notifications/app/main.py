import logging
import os
import random
import time

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Notifications Service")


class NotificationRequest(BaseModel):
    reservation_id: str
    email: str


class NotificationResponse(BaseModel):
    status: str
    reservation_id: str


def get_notification_delay() -> float:
    return max(0.0, float(os.getenv("NOTIFICATION_DELAY_SECONDS", "0")))


def get_notification_failure_rate() -> float:
    failure_rate = float(os.getenv("NOTIFICATION_FAILURE_RATE", "0"))
    if not 0.0 <= failure_rate <= 1.0:
        raise ValueError("NOTIFICATION_FAILURE_RATE debe estar entre 0 y 1")
    return failure_rate


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "healthy"}


@app.post("/notifications", response_model=NotificationResponse)
def create_notification(
    notification: NotificationRequest,
) -> NotificationResponse:
    delay = get_notification_delay()
    failure_rate = get_notification_failure_rate()

    logger.info(
        "Procesando notificación para reserva %s y correo %s",
        notification.reservation_id,
        notification.email,
    )
    time.sleep(delay)

    if random.random() < failure_rate:
        logger.warning(
            "Fallo simulado para reserva %s y correo %s",
            notification.reservation_id,
            notification.email,
        )
        raise HTTPException(
            status_code=503,
            detail="Notification service unavailable",
        )

    logger.info(
        "Notificación simulada enviada para reserva %s y correo %s",
        notification.reservation_id,
        notification.email,
    )
    return NotificationResponse(
        status="sent",
        reservation_id=notification.reservation_id,
    )
