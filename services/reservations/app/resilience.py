import asyncio
import time
from enum import StrEnum

import httpx


class InventoryConflictError(Exception):
    pass


class InventoryUnavailableError(Exception):
    pass


class PaymentUnavailableError(Exception):
    pass


class CircuitOpenError(Exception):
    pass


class CircuitState(StrEnum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class CircuitBreaker:
    def __init__(self, failure_threshold: int, recovery_seconds: float):
        self.failure_threshold = failure_threshold
        self.recovery_seconds = recovery_seconds
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.opened_at = 0.0

    def allow_request(self) -> bool:
        if self.state == CircuitState.CLOSED:
            return True

        if self.state == CircuitState.HALF_OPEN:
            return False

        if time.monotonic() - self.opened_at >= self.recovery_seconds:
            self.state = CircuitState.HALF_OPEN
            return True

        return False

    def record_success(self) -> None:
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.opened_at = 0.0

    def record_failure(self) -> None:
        if self.state == CircuitState.HALF_OPEN:
            self._open()
            return

        self.failure_count += 1
        if self.failure_count >= self.failure_threshold:
            self._open()

    def reset(self) -> None:
        self.record_success()

    def _open(self) -> None:
        self.state = CircuitState.OPEN
        self.opened_at = time.monotonic()


async def reserve_inventory(
    client: httpx.AsyncClient,
    inventory_url: str,
    event_id: int,
    timeout_seconds: float,
    max_attempts: int,
) -> None:
    backoffs = (0.5, 1.0, 2.0)
    attempts = max(1, max_attempts)

    for attempt in range(attempts):
        try:
            response = await client.post(
                f"{inventory_url}/inventory/{event_id}/reserve",
                timeout=timeout_seconds,
            )
            if response.status_code == 409:
                raise InventoryConflictError
            if response.is_success:
                return
            if response.status_code < 500:
                raise InventoryUnavailableError
        except (httpx.RequestError, httpx.TimeoutException):
            pass

        if attempt < attempts - 1:
            await asyncio.sleep(backoffs[min(attempt, len(backoffs) - 1)])

    raise InventoryUnavailableError


async def release_inventory(
    client: httpx.AsyncClient,
    inventory_url: str,
    event_id: int,
    timeout_seconds: float,
) -> bool:
    try:
        response = await client.post(
            f"{inventory_url}/inventory/{event_id}/release",
            timeout=timeout_seconds,
        )
    except (httpx.RequestError, httpx.TimeoutException):
        return False

    return response.is_success


async def process_payment(
    client: httpx.AsyncClient,
    payments_url: str,
    reservation_id: str,
    amount: float,
    timeout_seconds: float,
    circuit_breaker: CircuitBreaker,
) -> None:
    if not circuit_breaker.allow_request():
        raise CircuitOpenError

    try:
        response = await client.post(
            f"{payments_url}/payments",
            json={"reservation_id": reservation_id, "amount": amount},
            timeout=timeout_seconds,
        )
    except (httpx.RequestError, httpx.TimeoutException) as error:
        circuit_breaker.record_failure()
        raise PaymentUnavailableError from error

    if not response.is_success:
        circuit_breaker.record_failure()
        raise PaymentUnavailableError

    circuit_breaker.record_success()


async def send_notification(
    client: httpx.AsyncClient,
    notifications_url: str,
    reservation_id: str,
    email: str,
    timeout_seconds: float,
) -> bool:
    try:
        response = await client.post(
            f"{notifications_url}/notifications",
            json={"reservation_id": reservation_id, "email": email},
            timeout=timeout_seconds,
        )
    except (httpx.RequestError, httpx.TimeoutException):
        return False

    return response.is_success
