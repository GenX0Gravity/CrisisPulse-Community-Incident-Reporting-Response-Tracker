"""Idempotency management for CrisisPulse incident submissions.

Ensures repeated submissions with the same idempotency key return the original
incident without creating duplicate records or launching redundant workflows.
"""

from __future__ import annotations

import time
from typing import Any

from shared.config import IDEMPOTENCY_PREFIX


def extract_idempotency_key(event: dict, body: dict) -> str | None:
    """Extract idempotency key from headers or request payload."""
    headers = event.get("headers") or {}
    # Check common header variants (case-insensitive search)
    for h_key, h_val in headers.items():
        if h_key.lower() in ("idempotency-key", "x-idempotency-key"):
            if h_val and isinstance(h_val, str):
                return h_val.strip()

    # Check body field
    body_key = body.get("idempotencyKey")
    if body_key and isinstance(body_key, str):
        return body_key.strip()

    return None


def get_existing_idempotent_incident(
    table: Any, idempotency_key: str
) -> dict[str, Any] | None:
    """Retrieve existing incident associated with an idempotency key if present."""
    idemp_pk = f"{IDEMPOTENCY_PREFIX}{idempotency_key}"
    try:
        res = table.get_item(Key={"incidentId": idemp_pk})
        item = res.get("Item")
        if not item:
            return None

        target_id = item.get("targetIncidentId")
        if not target_id:
            return None

        # Fetch the canonical incident
        inc_res = table.get_item(Key={"incidentId": target_id})
        return inc_res.get("Item")
    except Exception:
        return None


def record_idempotency_key(
    table: Any, idempotency_key: str, incident_id: str
) -> bool:
    """Store idempotency mapping record in DynamoDB.

    Uses a conditional write to prevent race conditions.
    """
    idemp_pk = f"{IDEMPOTENCY_PREFIX}{idempotency_key}"
    now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    try:
        table.put_item(
            Item={
                "incidentId": idemp_pk,
                "targetIncidentId": incident_id,
                "createdAt": now_iso,
                "ttl": int(time.time()) + 86400,  # 24-hour expiration
            },
            ConditionExpression="attribute_not_exists(incidentId)",
        )
        return True
    except Exception:
        return False
