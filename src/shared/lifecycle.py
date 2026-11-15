"""CrisisPulse incident lifecycle and status transition management.

Canonical Statuses:
  - Reported: Initial submission awaiting triage.
  - Under Review: Automated triage and duplicate check completed; under evaluation.
  - In Progress: Active field or emergency response in progress.
  - Resolved: Incident stabilized, mitigated, or resolved.
"""

from __future__ import annotations

import time
from typing import Any

CANONICAL_STATUSES: set[str] = {
    "Reported",
    "Under Review",
    "In Progress",
    "Resolved",
}

# Normalization mapping for case-insensitivity and legacy status strings
STATUS_NORMALIZATION_MAP: dict[str, str] = {
    "reported": "Reported",
    "under review": "Under Review",
    "under_review": "Under Review",
    "in progress": "In Progress",
    "in_progress": "In Progress",
    "resolved": "Resolved",
    # Legacy mappings
    "submitted": "Reported",
    "processing": "Reported",
    "triaged": "Under Review",
    "flagged_duplicate": "Under Review",
    "investigating": "In Progress",
    "dismissed": "Resolved",
}

# Enforced Lifecycle State Transitions
ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "Reported": {"Under Review"},
    "Under Review": {"In Progress", "Resolved"},
    "In Progress": {"Resolved", "Under Review"},
    "Resolved": {"In Progress"},  # Re-opening if re-ignited or condition recurs
}


def normalize_status(status_str: str) -> str | None:
    """Normalize input status string to canonical title-case status."""
    if not status_str or not isinstance(status_str, str):
        return None
    cleaned = status_str.strip().lower()
    return STATUS_NORMALIZATION_MAP.get(cleaned)


def is_valid_transition(current_status: str, target_status: str) -> bool:
    """Validate whether transitioning from current_status to target_status is allowed."""
    current_norm = normalize_status(current_status)
    target_norm = normalize_status(target_status)

    if not current_norm or not target_norm:
        return False

    # No-op transition is allowed
    if current_norm == target_norm:
        return True

    allowed_targets = ALLOWED_TRANSITIONS.get(current_norm, set())
    return target_norm in allowed_targets


def create_history_entry(
    status: str,
    actor: str = "system",
    notes: str = "",
    timestamp_iso: str | None = None,
) -> dict[str, Any]:
    """Create a structured status history entry."""
    norm_status = normalize_status(status) or status
    now_iso = timestamp_iso or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    return {
        "status": norm_status,
        "timestamp": now_iso,
        "actor": actor,
        "notes": notes,
    }
