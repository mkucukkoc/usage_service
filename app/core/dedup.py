from typing import Dict

from google.cloud import firestore

from app.config.logger import get_logger

LOGGER = get_logger("usage_service.dedup")

def acquire_request_lock(
    db: firestore.Client,
    request_id: str,
    metadata: Dict,
) -> bool:
    """Atomically create request_dedup/{requestId}.

    Returns:
        True if the lock was acquired (first request).
        False if the requestId already exists.
    """

    LOGGER.info(
        "Dedup lock attempt",
        extra={"requestId": request_id, "metadata": metadata},
    )
    doc_ref = db.collection("request_dedup").document(request_id)

    @firestore.transactional
    def _txn(transaction: firestore.Transaction) -> bool:
        snapshot = doc_ref.get(transaction=transaction)
        if snapshot.exists:
            LOGGER.info("Dedup lock exists; skipping", extra={"requestId": request_id})
            return False
        transaction.set(doc_ref, metadata, merge=True)
        LOGGER.info("Dedup lock acquired", extra={"requestId": request_id})
        return True

    transaction = db.transaction()
    result = _txn(transaction)
    LOGGER.info("Dedup lock result", extra={"requestId": request_id, "acquired": result})
    return result
