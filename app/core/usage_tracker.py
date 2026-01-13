import datetime as dt
import os
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, Optional

from google.cloud import firestore

from app.config.logger import get_logger
from .dedup import acquire_request_lock

DEFAULT_EXECUTOR = ThreadPoolExecutor(max_workers=4)
LOGGER = get_logger("usage_service.usage_tracking")
DEBUG_LOGS = os.getenv("USAGE_TRACKING_DEBUG", "").lower() in ("1", "true", "yes", "on")
WRITE_RAW_EVENTS = os.getenv("WRITE_RAW_EVENTS", "").lower() in ("1", "true", "yes", "on")


def log_event(db: firestore.Client, event: Dict[str, Any]) -> None:
    """Write a raw usage event document.

    Firestore path: usage_events/{eventId}
    """

    event_id = event.get("eventId") or event["requestId"]
    LOGGER.info(
        "UsageTracking log_event start",
        extra={
            "eventId": event_id,
            "requestId": event.get("requestId"),
            "userId": event.get("userId"),
            "endpoint": event.get("endpoint"),
        },
    )
    doc_ref = db.collection("usage_events").document(event_id)
    payload = dict(event)
    payload.setdefault("loggedAt", firestore.SERVER_TIMESTAMP)
    if DEBUG_LOGS:
        LOGGER.info(
            "UsageTracking log_event payload prepared",
            extra={
                "eventId": event_id,
                "path": f"usage_events/{event_id}",
                "payload": payload,
            },
        )
    doc_ref.set(payload, merge=True)
    LOGGER.info(
        "UsageTracking log_event done",
        extra={"eventId": event_id, "userId": event.get("userId")},
    )


def update_aggregates(db: firestore.Client, event: Dict[str, Any]) -> bool:
    """Update daily and monthly aggregates if requestId is new.

    Returns:
        True if aggregates were updated.
        False if requestId already existed (idempotent skip).
    """

    request_id = event["requestId"]
    user_id = event["userId"]
    timestamp = _parse_timestamp(event["timestamp"])
    day_key = timestamp.strftime("%Y%m%d")
    month_key = timestamp.strftime("%Y%m")

    LOGGER.info(
        "UsageTracking update_aggregates start",
        extra={
            "requestId": request_id,
            "userId": user_id,
            "day": day_key,
            "month": month_key,
        },
    )
    if not acquire_request_lock(
        db,
        request_id,
        {
            "userId": user_id,
            "endpoint": event.get("endpoint"),
            "createdAt": firestore.SERVER_TIMESTAMP,
        },
    ):
        if DEBUG_LOGS:
            LOGGER.info(
                "UsageTracking dedup skip (requestId already exists)",
                extra={"requestId": request_id, "userId": user_id},
            )
        return False

    daily_ref = db.collection("usage_daily").document(f"{user_id}_{day_key}")
    monthly_ref = db.collection("usage_monthly").document(f"{user_id}_{month_key}")

    @firestore.transactional
    def _txn(transaction: firestore.Transaction) -> None:
        daily_snapshot = daily_ref.get(transaction=transaction)
        monthly_snapshot = monthly_ref.get(transaction=transaction)

        daily_update = _build_aggregate_update(event, daily_snapshot, day_key=day_key)
        monthly_update = _build_aggregate_update(
            event,
            monthly_snapshot,
            month_key=month_key,
            is_monthly=True,
        )

        if DEBUG_LOGS:
            LOGGER.info(
                "UsageTracking aggregate updates prepared",
                extra={
                    "requestId": request_id,
                    "userId": user_id,
                    "day": day_key,
                    "month": month_key,
                    "daily_exists": daily_snapshot.exists,
                    "monthly_exists": monthly_snapshot.exists,
                },
            )

        transaction.set(daily_ref, daily_update, merge=True)
        transaction.set(monthly_ref, monthly_update, merge=True)

    transaction = db.transaction()
    _txn(transaction)
    LOGGER.info(
        "UsageTracking aggregate updates committed",
        extra={
            "requestId": request_id,
            "userId": user_id,
            "day": day_key,
            "month": month_key,
        },
    )
    return True


def enqueue_usage_update(db: firestore.Client, event: Dict[str, Any]) -> None:
    """Fire-and-forget helper to log events and update aggregates."""

    def _work() -> None:
        try:
            updated = update_aggregates(db, event)
        except Exception as exc:  # noqa: BLE001
            LOGGER.warning(
                "UsageTracking update_aggregates failed",
                extra={
                    "requestId": event.get("requestId"),
                    "userId": event.get("userId"),
                    "error": str(exc),
                },
                exc_info=DEBUG_LOGS,
            )
            return
        if updated and WRITE_RAW_EVENTS:
            try:
                log_event(db, event)
            except Exception as exc:  # noqa: BLE001
                LOGGER.warning(
                    "UsageTracking log_event failed",
                    extra={
                        "requestId": event.get("requestId"),
                        "userId": event.get("userId"),
                        "error": str(exc),
                    },
                    exc_info=DEBUG_LOGS,
                )

    LOGGER.info(
        "UsageTracking enqueue_usage_update submit",
        extra={
            "requestId": event.get("requestId"),
            "userId": event.get("userId"),
            "endpoint": event.get("endpoint"),
        },
    )
    DEFAULT_EXECUTOR.submit(_work)


def _build_aggregate_update(
    event: Dict[str, Any],
    snapshot: firestore.DocumentSnapshot,
    day_key: Optional[str] = None,
    month_key: Optional[str] = None,
    is_monthly: bool = False,
) -> Dict[str, Any]:
    now = firestore.SERVER_TIMESTAMP
    update: Dict[str, Any] = {
        "userId": event["userId"],
        "lastEventAt": event["timestamp"],
        "updatedAt": now,
    }

    if is_monthly:
        update["month"] = month_key
    else:
        update["day"] = day_key

    input_tokens = event.get("inputTokens", 0) or 0
    output_tokens = event.get("outputTokens", 0) or 0
    cost_try = event.get("costTRY")
    cost_local = (event.get("cost") or {}).get("amount", 0.0) or 0.0
    cost_usd = event.get("costUSD", 0.0) or 0.0
    currency = (event.get("cost") or {}).get("currency")
    resolved_cost_try = cost_try if cost_try is not None else (cost_local if currency == "TRY" else 0.0)

    update.update(
        {
            "totalInputTokens": firestore.Increment(input_tokens),
            "totalOutputTokens": firestore.Increment(output_tokens),
            "totalCostTry": firestore.Increment(resolved_cost_try),
            "totalCostUsd": firestore.Increment(cost_usd),
        }
    )

    action = event.get("action")
    if action:
        action_update = {
            "tokensIn": firestore.Increment(input_tokens),
            "tokensOut": firestore.Increment(output_tokens),
            "costTry": firestore.Increment(resolved_cost_try),
            "costUsd": firestore.Increment(cost_usd),
        }
        update.setdefault("actions", {}).setdefault(action, {}).update(action_update)

    plan_snapshot = event.get("plan")
    if plan_snapshot:
        update["planSnapshot"] = plan_snapshot

    return update


def _parse_timestamp(value: Any) -> dt.datetime:
    if isinstance(value, dt.datetime):
        return value
    if isinstance(value, (int, float)):
        return dt.datetime.utcfromtimestamp(value)
    return dt.datetime.utcfromtimestamp(int(value))
