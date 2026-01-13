import uuid

from fastapi import FastAPI, Request

from app.config.logger import get_logger, setup_logging
from app.api.routes_health import router as health_router
from app.api.routes_usage import router as usage_router

setup_logging()
LOGGER = get_logger("usage_service.request")

app = FastAPI(title="Usage Service", version="1.0.0")


@app.middleware("http")
async def log_requests(request: Request, call_next):
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id
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
    response = await call_next(request)
    LOGGER.info(
        "Response status: %s (Request ID: %s)",
        response.status_code,
        request_id,
    )
    return response


app.include_router(health_router)
app.include_router(usage_router)
