#!/usr/bin/env python3

import asyncio
import json
import shutil
import subprocess
import sys
import time

try:
    import httpx
except ImportError:
    print("Error: se requiere httpx y no está disponible.", file=sys.stderr)
    sys.exit(1)

NAMESPACE = "tickets"
GATEWAY_URL = "http://localhost:8080"
INVENTORY_URL = "http://localhost:18000"


async def wait_for_inventory(
    process: subprocess.Popen[bytes],
    client: httpx.AsyncClient,
) -> None:
    for _ in range(20):
        if process.poll() is not None:
            raise RuntimeError("kubectl port-forward terminó inesperadamente")
        try:
            response = await client.get(f"{INVENTORY_URL}/health")
            if response.is_success:
                return
        except httpx.RequestError:
            pass
        await asyncio.sleep(0.5)
    raise RuntimeError("no fue posible acceder a la API de Inventario")


async def reset_inventory_to_one() -> None:
    print("Abriendo acceso temporal a la API de Inventario...")
    process = subprocess.Popen(
        [
            "kubectl",
            "-n",
            NAMESPACE,
            "port-forward",
            "service/inventory",
            "18000:8000",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    try:
        async with httpx.AsyncClient(timeout=5) as client:
            await wait_for_inventory(process, client)
            response = await client.post(
                f"{INVENTORY_URL}/inventory/1/reset",
                json={"available_seats": 1},
            )
            response.raise_for_status()
            print(f"Inventario preparado: {response.text}")
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()


async def create_reservation(
    client: httpx.AsyncClient,
    start_event: asyncio.Event,
    email: str,
) -> tuple[str, int, str, float]:
    await start_event.wait()
    started_at = time.perf_counter()
    response = await client.post(
        f"{GATEWAY_URL}/api/reservations",
        json={
            "event_id": 1,
            "email": email,
            "amount": 49.99,
        },
    )
    duration = time.perf_counter() - started_at
    return email, response.status_code, response.text, duration


async def run_scenario() -> bool:
    await reset_inventory_to_one()

    start_event = asyncio.Event()
    async with httpx.AsyncClient(timeout=15) as client:
        tasks = [
            asyncio.create_task(
                create_reservation(
                    client,
                    start_event,
                    "race-one@example.com",
                )
            ),
            asyncio.create_task(
                create_reservation(
                    client,
                    start_event,
                    "race-two@example.com",
                )
            ),
        ]

        await asyncio.sleep(0)
        print("Lanzando dos reservas concurrentes...")
        start_event.set()
        results = await asyncio.gather(*tasks)

        for email, status_code, body, duration in results:
            print(f"Solicitud de {email}:")
            print(f"  HTTP: {status_code}")
            print(f"  Duración: {duration:.3f} s")
            print(f"  Cuerpo: {body}")

        inventory_response = await client.get(
            f"{GATEWAY_URL}/api/inventory/1"
        )
        inventory_response.raise_for_status()
        inventory = inventory_response.json()

    print("Inventario final:")
    print(json.dumps(inventory, ensure_ascii=False))

    status_codes = [result[1] for result in results]
    exactly_one_created = status_codes.count(201) == 1
    exactly_one_conflict = status_codes.count(409) == 1
    inventory_is_zero = inventory.get("available_seats") == 0

    if not exactly_one_created:
        print("Error: se esperaba exactamente una respuesta HTTP 201.")
    if not exactly_one_conflict:
        print("Error: se esperaba exactamente una respuesta HTTP 409.")
    if not inventory_is_zero:
        print("Error: el inventario final debía ser cero.")

    return exactly_one_created and exactly_one_conflict and inventory_is_zero


def main() -> int:
    if shutil.which("kubectl") is None:
        print("Error: se requiere kubectl y no está disponible.", file=sys.stderr)
        return 1

    try:
        successful = asyncio.run(run_scenario())
    except (httpx.HTTPError, RuntimeError, OSError) as error:
        print(f"Error durante el escenario: {error}", file=sys.stderr)
        return 1

    if not successful:
        return 1

    print("Condición de carrera controlada correctamente.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
