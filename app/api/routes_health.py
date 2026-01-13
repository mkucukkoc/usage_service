from fastapi import APIRouter

from app.config.logger import get_logger

router = APIRouter()
LOGGER = get_logger("usage_service.routes.health")


@router.get("/health")
async def health_check() -> dict:
    LOGGER.info("Health check requested")
    return {"ok": True}
