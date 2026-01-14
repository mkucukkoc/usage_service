import hmac
import os

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from google.cloud import firestore

from app.config.logger import get_logger
from app.core.usage_tracker import log_event, update_aggregates
from app.core.event_builder import enrich_usage_event
from app.db.firestore import get_firestore_client
from app.schemas.responses import UsageIngestResponse
from app.schemas.usage_event import UsageEvent

router = APIRouter()
LOGGER = get_logger("usage_service.routes.usage")


@router.post("/v1/usage/events", response_model=UsageIngestResponse)
async def ingest_usage_event(
    payload: UsageEvent,
    x_internal_key: str | None = Header(default=None, alias="X-Internal-Key"),
    db: firestore.Client = Depends(get_firestore_client),
    request: Request = None,
) -> UsageIngestResponse:
    event = payload.dict()
    event = enrich_usage_event(event)
    event.setdefault("eventId", event["requestId"])
    LOGGER.info(
        "Usage ingest request received",
        extra={
            "requestId": event.get("requestId"),
            "eventId": event.get("eventId"),
            "userId": event.get("userId"),
            "endpoint": event.get("endpoint"),
            "headers": dict(request.headers) if request else {},
        },
    )

    if _is_auth_required() and not _is_valid_internal_key(x_internal_key):
        LOGGER.warning(
            "Usage ingest unauthorized",
            extra={"requestId": event.get("requestId")},
        )
        raise HTTPException(status_code=401, detail="Unauthorized")
    updated = update_aggregates(db, event)
    LOGGER.info(
        "Usage ingest aggregate update result",
        extra={
            "requestId": event.get("requestId"),
            "updated": updated,
            "writeRawEvents": _write_raw_events(),
        },
    )
    if updated and _write_raw_events():
        log_event(db, event)
        LOGGER.info(
            "Usage ingest raw event logged",
            extra={"requestId": event.get("requestId"), "eventId": event.get("eventId")},
        )
    return UsageIngestResponse(
        ok=True,
        deduped=not updated,
        requestId=event["requestId"],
        eventId=event["eventId"],
    )


def _is_auth_required() -> bool:
    return bool(_internal_key())


def _internal_key() -> str | None:
    return os.getenv("USAGE_SERVICE_INTERNAL_KEY")


def _is_valid_internal_key(header_key: str | None) -> bool:
    expected = _internal_key()
    if not expected:
        return True
    if header_key is None:
        return False
    return hmac.compare_digest(header_key, expected)


def _write_raw_events() -> bool:
    return os.getenv("WRITE_RAW_EVENTS", "").lower() in ("1", "true", "yes", "on")
