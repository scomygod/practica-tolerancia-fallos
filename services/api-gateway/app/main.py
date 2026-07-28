import logging
import os
from collections.abc import AsyncGenerator

import httpx
from fastapi import Depends, FastAPI, Request, Response
from fastapi.responses import JSONResponse

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

RESERVATIONS_URL = os.environ["RESERVATIONS_URL"].rstrip("/")
INVENTORY_URL = os.environ["INVENTORY_URL"].rstrip("/")
GATEWAY_TIMEOUT_SECONDS = float(
    os.getenv("GATEWAY_TIMEOUT_SECONDS", "10")
)

app = FastAPI(title="API Gateway")


async def get_http_client() -> AsyncGenerator[httpx.AsyncClient, None]:
    async with httpx.AsyncClient() as client:
        yield client


async def forward_request(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    body: bytes | None = None,
    content_type: str | None = None,
) -> Response:
    headers = {"content-type": content_type} if content_type else None

    try:
        upstream_response = await client.request(
            method=method,
            url=url,
            content=body,
            headers=headers,
            timeout=GATEWAY_TIMEOUT_SECONDS,
        )
    except httpx.RequestError as error:
        logger.warning("Servicio destino inaccesible: %s", url)
        return JSONResponse(
            status_code=503,
            content={"detail": "Upstream service unavailable"},
        )

    response_headers = {}
    if "content-type" in upstream_response.headers:
        response_headers["content-type"] = upstream_response.headers[
            "content-type"
        ]

    return Response(
        content=upstream_response.content,
        status_code=upstream_response.status_code,
        headers=response_headers,
    )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "healthy"}


@app.post("/api/reservations")
async def create_reservation(
    request: Request,
    client: httpx.AsyncClient = Depends(get_http_client),
) -> Response:
    return await forward_request(
        client=client,
        method="POST",
        url=f"{RESERVATIONS_URL}/reservations",
        body=await request.body(),
        content_type=request.headers.get("content-type"),
    )


@app.get("/api/reservations/{reservation_id}")
async def get_reservation(
    reservation_id: str,
    client: httpx.AsyncClient = Depends(get_http_client),
) -> Response:
    return await forward_request(
        client=client,
        method="GET",
        url=f"{RESERVATIONS_URL}/reservations/{reservation_id}",
    )


@app.get("/api/inventory/{event_id}")
async def get_inventory(
    event_id: int,
    client: httpx.AsyncClient = Depends(get_http_client),
) -> Response:
    return await forward_request(
        client=client,
        method="GET",
        url=f"{INVENTORY_URL}/inventory/{event_id}",
    )
