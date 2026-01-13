import base64
import json
import os
from typing import Optional

from google.cloud import firestore
from google.oauth2 import service_account

from app.config.logger import get_logger

LOGGER = get_logger("usage_service.firestore")


def get_firestore_client() -> firestore.Client:
    LOGGER.info("Firestore client initialization started")
    service_account_base64 = os.getenv("FIREBASE_SERVICE_ACCOUNT_BASE64")
    if not service_account_base64:
        LOGGER.info("FIREBASE_SERVICE_ACCOUNT_BASE64 not set; using default credentials")
        return firestore.Client()

    try:
        decoded_json = base64.b64decode(service_account_base64).decode("utf-8")
        payload = json.loads(decoded_json)
    except (ValueError, json.JSONDecodeError) as exc:
        LOGGER.error("Invalid FIREBASE_SERVICE_ACCOUNT_BASE64 payload: %s", exc)
        raise

    credentials = service_account.Credentials.from_service_account_info(payload)
    project_id: Optional[str] = payload.get("project_id")
    LOGGER.info("Firestore client initialized with explicit credentials")
    return firestore.Client(credentials=credentials, project=project_id)
