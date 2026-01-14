import json
import uuid
from typing import Any

from fastapi import FastAPI, Request, Response

from app.config.logger import get_logger, setup_logging
from app.api.routes_health import router as health_router
from app.api.routes_usage import router as usage_router

setup_logging()
LOGGER = get_logger("usage_service.request")

app = FastAPI(title="Usage Service", version="1.0.0")


def _json_pretty(obj: Any) -> str:
    try:
        return json.dumps(obj, indent=2, ensure_ascii=False)
    except Exception:
        try:
            return str(obj)
        except Exception:
            return "<unserializable>"


@app.middleware("http")
async def log_requests(request: Request, call_next):
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id

    # Quiet health checks: skip verbose logging to reduce noise.
    if request.url.path == "/health":
        response = await call_next(request)
        LOGGER.debug(
            "Health check request skipped verbose logging",
            extra={"requestId": request_id, "status": response.status_code},
        )
        return response

    raw_body = await request.body()

    async def receive() -> dict:
        return {"type": "http.request", "body": raw_body, "more_body": False}

    request._receive = receive  # type: ignore[attr-defined]

    request_json: Any = None
    if raw_body:
        try:
            request_json = json.loads(raw_body.decode("utf-8"))
        except Exception:
            request_json = raw_body.decode("utf-8", errors="ignore")

    LOGGER.info(
        "Incoming request: %s %s (Request ID: %s)",
        request.method,
        request.url,
        request_id,
    )
    LOGGER.info(
        "Request headers: %s (Request ID: %s)",
        dict(request.headers),
        request_id,
    )
    if request_json is not None:
        LOGGER.info(
            "Request body (Request ID: %s):\n%s",
            request_id,
            _json_pretty(request_json),
        )

    response = await call_next(request)

    resp_body = b""
    async for chunk in response.body_iterator:
        resp_body += chunk

    response_json: Any = None
    if resp_body:
        try:
            response_json = json.loads(resp_body.decode("utf-8"))
        except Exception:
            response_json = resp_body.decode("utf-8", errors="ignore")

    LOGGER.info(
        "Response status: %s (Request ID: %s)",
        response.status_code,
        request_id,
    )
    if response_json is not None:
        LOGGER.info(
            "Response body (Request ID: %s):\n%s",
            request_id,
            _json_pretty(response_json),
        )

    return Response(
        content=resp_body,
        status_code=response.status_code,
        headers=dict(response.headers),
        media_type=response.media_type,
        background=response.background,
    )


app.include_router(health_router)
app.include_router(usage_router)
