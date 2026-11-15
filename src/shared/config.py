"""Centralised configuration loaded from environment variables."""

import os

TABLE_NAME: str = os.environ.get("TABLE_NAME", "CrisisPulse-incidents")
PHOTO_BUCKET: str = os.environ.get("PHOTO_BUCKET", "")
DEMO_MODE: bool = os.environ.get("DEMO_MODE", "true").lower() == "true"
FRONTEND_ORIGIN: str = os.environ.get("FRONTEND_ORIGIN", "http://localhost:3000")
MAX_IMAGE_SIZE_MB: int = int(os.environ.get("MAX_IMAGE_SIZE_MB", "5"))
MAX_IMAGE_SIZE_BYTES: int = MAX_IMAGE_SIZE_MB * 1024 * 1024
PRESIGNED_URL_EXPIRY_SEC: int = int(os.environ.get("PRESIGNED_URL_EXPIRY_SEC", "300"))
STATE_MACHINE_ARN: str = os.environ.get("STATE_MACHINE_ARN", "")

# GSI names
CREATED_AT_INDEX: str = "createdAt-index"
CATEGORY_CREATED_AT_INDEX: str = "category-createdAt-index"

# DynamoDB entity partition marker
ENTITY_TYPE: str = "INCIDENT"
IDEMPOTENCY_PREFIX: str = "IDEMP#"

ALLOWED_CONTENT_TYPES: set[str] = {"image/jpeg", "image/png", "image/webp"}

# Duplicate detection threshold in meters
DUPLICATE_DISTANCE_METERS: float = 300.0
# Duplicate detection time window in seconds (24 hours)
DUPLICATE_TIME_WINDOW_SEC: int = 86400
