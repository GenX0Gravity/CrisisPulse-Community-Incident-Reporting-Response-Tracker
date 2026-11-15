"""Step Functions task handler: deterministic scoring, duplicate detection, and photo validation."""

from __future__ import annotations

import time
from typing import Any

from shared.config import (
    TABLE_NAME,
    PHOTO_BUCKET,
    DEMO_MODE,
    MAX_IMAGE_SIZE_BYTES,
)
from shared.duplicate_detection import find_duplicate_incidents
from shared.lifecycle import create_history_entry
from shared.scoring import calculate_priority_score

try:
    import boto3
    dynamodb = boto3.resource("dynamodb")
    table = dynamodb.Table(TABLE_NAME)
    s3 = boto3.client("s3")
except Exception:
    boto3 = None
    dynamodb = None
    table = None
    s3 = None


def _validate_photo(photo_key: str) -> dict[str, Any]:
    """Validate photo attachment in S3 without public bucket access."""
    if not photo_key:
        return {
            "attached": False,
            "valid": True,
            "reason": "No photo was attached to this report.",
        }

    if DEMO_MODE:
        return {
            "attached": True,
            "valid": True,
            "demoBypass": True,
            "reason": "Demo mode active — S3 head_object verification bypassed.",
        }

    if not s3:
        return {
            "attached": True,
            "valid": True,
            "reason": "S3 client not initialized in current environment.",
        }

    try:
        resp = s3.head_object(Bucket=PHOTO_BUCKET, Key=photo_key)
        size_bytes = resp.get("ContentLength", 0)
        content_type = resp.get("ContentType", "")

        if size_bytes > MAX_IMAGE_SIZE_BYTES:
            return {
                "attached": True,
                "valid": False,
                "sizeBytes": size_bytes,
                "reason": (
                    f"Photo size ({size_bytes} bytes) exceeds maximum allowable limit "
                    f"of {MAX_IMAGE_SIZE_BYTES} bytes."
                ),
            }

        return {
            "attached": True,
            "valid": True,
            "sizeBytes": size_bytes,
            "contentType": content_type,
            "reason": "Photo verified in private S3 bucket.",
        }
    except Exception as exc:
        return {
            "attached": True,
            "valid": False,
            "reason": f"Photo object could not be verified in S3: {exc}",
        }


def handler(event: dict, context: Any) -> dict[str, Any]:
    """Invoked by Step Functions to process and enrich an incident report."""
    incident_id = event["incidentId"]
    category = event.get("category", "other")
    risk_factors = event.get("riskFactors") or []
    lat = event.get("latitude")
    lon = event.get("longitude")
    photo_key = event.get("photoKey", "")
    created_at = event.get("createdAt")

    # 1. Deterministic Priority Scoring (rule-based, no AI claims)
    scoring = calculate_priority_score(category, risk_factors)

    # 2. Bounded Duplicate Detection (GSI query, 24-hr window, <= 300m)
    dup_result = find_duplicate_incidents(
        table=table,
        incident_id=incident_id,
        category=category,
        latitude=float(lat) if lat is not None else None,
        longitude=float(lon) if lon is not None else None,
        current_time_iso=created_at,
    )

    # 3. Photo Validation
    photo_result = _validate_photo(photo_key)

    # 4. Canonical Status Transition: Reported -> Under Review
    status = "Under Review"
    processed_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    history_notes = (
        f"Automated evaluation completed: {scoring['priority']} Priority ({scoring['score']}/100). "
        f"{dup_result['reason']}"
    )

    history_entry = create_history_entry(
        status=status,
        actor="step-functions",
        notes=history_notes,
        timestamp_iso=processed_at,
    )

    return {
        "incidentId": incident_id,
        "status": status,
        "priority": scoring["priority"],
        "priorityScore": scoring["score"],
        "priorityExplanation": scoring["explanation"],
        "scoringBreakdown": scoring["breakdown"],
        "isPotentialDuplicate": dup_result["isPotentialDuplicate"],
        "duplicateCount": dup_result["duplicateCount"],
        "duplicateCandidates": dup_result["candidates"],
        "duplicateReason": dup_result["reason"],
        "photoValidation": photo_result,
        "historyEntry": history_entry,
        "processedAt": processed_at,
    }
