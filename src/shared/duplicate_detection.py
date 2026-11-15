"""Duplicate incident detection for CrisisPulse.

Identifies potential duplicate reports within a 24-hour window and 300-meter
radius using a DynamoDB GSI bounded query (Key: category, SortKey: createdAt >= cutoff).
Never performs a full table scan.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone, timedelta
from typing import Any

try:
    from boto3.dynamodb.conditions import Key
except ImportError:
    # Graceful mock for local test environments without boto3 installed
    class Key:  # type: ignore[no-redef]
        def __init__(self, name: str):
            self.name = name

        def eq(self, val: Any) -> Key:
            return self

        def gte(self, val: Any) -> Key:
            return self

        def __and__(self, other: Any) -> Key:
            return self

from shared.config import (
    CATEGORY_CREATED_AT_INDEX,
    DUPLICATE_DISTANCE_METERS,
    DUPLICATE_TIME_WINDOW_SEC,
)

EARTH_RADIUS_METERS = 6371000.0


def calculate_haversine_distance(
    lat1: float, lon1: float, lat2: float, lon2: float
) -> float:
    """Calculate the great-circle distance between two points on Earth in meters.

    Uses the standard Haversine formula.
    """
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return EARTH_RADIUS_METERS * c


def find_duplicate_incidents(
    table: Any,
    incident_id: str,
    category: str,
    latitude: float | None,
    longitude: float | None,
    current_time_iso: str | None = None,
) -> dict[str, Any]:
    """Perform a bounded query on DynamoDB to find duplicate incidents within 300m and 24 hours.

    Uses GSI 'category-createdAt-index' with:
        KeyConditionExpression: category = :cat AND createdAt >= :cutoff
    This strictly avoids any full-table scan.
    """
    # If no coordinates are provided, spatial proximity cannot be checked
    if latitude is None or longitude is None:
        return {
            "isPotentialDuplicate": False,
            "duplicateCount": 0,
            "candidates": [],
            "reason": "No coordinates provided; spatial proximity check skipped.",
        }

    # Determine 24-hour cutoff
    if current_time_iso:
        try:
            now = datetime.fromisoformat(current_time_iso.replace("Z", "+00:00"))
        except ValueError:
            now = datetime.now(timezone.utc)
    else:
        now = datetime.now(timezone.utc)

    cutoff = now - timedelta(seconds=DUPLICATE_TIME_WINDOW_SEC)
    cutoff_iso = cutoff.strftime("%Y-%m-%dT%H:%M:%SZ")

    try:
        # Bounded query using GSI: Partition Key = category, Sort Key >= cutoff_iso
        query_response = table.query(
            IndexName=CATEGORY_CREATED_AT_INDEX,
            KeyConditionExpression=Key("category").eq(category)
            & Key("createdAt").gte(cutoff_iso),
            ScanIndexForward=False,  # Newest first
            Limit=50,  # Bounded search window
        )
    except Exception as exc:
        return {
            "isPotentialDuplicate": False,
            "duplicateCount": 0,
            "candidates": [],
            "reason": f"Bounded duplicate query failed: {exc}",
        }

    items = query_response.get("Items", [])
    duplicates: list[dict[str, Any]] = []

    for item in items:
        # Exclude self
        cand_id = item.get("incidentId")
        if not cand_id or cand_id == incident_id:
            continue

        cand_lat = item.get("latitude")
        cand_lon = item.get("longitude")
        if cand_lat is None or cand_lon is None:
            continue

        try:
            cand_lat_f = float(cand_lat)
            cand_lon_f = float(cand_lon)
        except (ValueError, TypeError):
            continue

        distance = calculate_haversine_distance(
            latitude, longitude, cand_lat_f, cand_lon_f
        )

        if distance <= DUPLICATE_DISTANCE_METERS:
            duplicates.append({
                "incidentId": cand_id,
                "title": item.get("title", ""),
                "category": item.get("category", ""),
                "distanceMeters": round(distance, 1),
                "createdAt": item.get("createdAt", ""),
                "status": item.get("status", ""),
            })

    is_duplicate = len(duplicates) > 0
    if is_duplicate:
        nearest = min(duplicates, key=lambda d: d["distanceMeters"])
        reason = (
            f"Detected {len(duplicates)} matching report(s) in category '{category}' "
            f"within 24 hours. Nearest incident '{nearest['incidentId']}' is {nearest['distanceMeters']}m away."
        )
    else:
        reason = f"No duplicate reports found in category '{category}' within 300m in the last 24 hours."

    return {
        "isPotentialDuplicate": is_duplicate,
        "duplicateCount": len(duplicates),
        "candidates": duplicates,
        "reason": reason,
    }
