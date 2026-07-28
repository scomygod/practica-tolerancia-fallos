import logging
import os
import random
import time
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Payments Service")


class PaymentRequest(BaseModel):
    reservation_id: str
    amount: float


class PaymentResponse(BaseModel):
    status: str
    reservation_id: str
    transaction_id: str


def get_payment_delay() -> float:
    return max(0.0, float(os.getenv("PAYMENT_DELAY_SECONDS", "0")))


def get_payment_failure_rate() -> float:
    failure_rate = float(os.getenv("PAYMENT_FAILURE_RATE", "0"))
    if not 0.0 <= failure_rate <= 1.0:
        raise ValueError("PAYMENT_FAILURE_RATE debe estar entre 0 y 1")
    return failure_rate


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "healthy"}


@app.post("/payments", response_model=PaymentResponse)
def create_payment(payment: PaymentRequest) -> PaymentResponse:
    delay = get_payment_delay()
    failure_rate = get_payment_failure_rate()

    logger.info(
        "Procesando pago para reserva %s por %.2f",
        payment.reservation_id,
        payment.amount,
    )
    time.sleep(delay)

    if random.random() < failure_rate:
        logger.warning("Fallo simulado para reserva %s", payment.reservation_id)
        raise HTTPException(status_code=503, detail="Payment service unavailable")

    transaction_id = str(uuid4())
    logger.info(
        "Pago aprobado para reserva %s, transacción %s",
        payment.reservation_id,
        transaction_id,
    )
    return PaymentResponse(
        status="approved",
        reservation_id=payment.reservation_id,
        transaction_id=transaction_id,
    )
