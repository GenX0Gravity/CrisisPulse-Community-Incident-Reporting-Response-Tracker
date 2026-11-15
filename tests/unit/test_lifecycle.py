"""Unit tests for incident lifecycle and status transition enforcement."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

from shared.lifecycle import (
    CANONICAL_STATUSES,
    create_history_entry,
    is_valid_transition,
    normalize_status,
)


def test_canonical_statuses_set():
    assert "Reported" in CANONICAL_STATUSES
    assert "Under Review" in CANONICAL_STATUSES
    assert "In Progress" in CANONICAL_STATUSES
    assert "Resolved" in CANONICAL_STATUSES
    assert len(CANONICAL_STATUSES) == 4


def test_status_normalization():
    assert normalize_status("reported") == "Reported"
    assert normalize_status("REPORTED") == "Reported"
    assert normalize_status("under review") == "Under Review"
    assert normalize_status("under_review") == "Under Review"
    assert normalize_status("in progress") == "In Progress"
    assert normalize_status("in_progress") == "In Progress"
    assert normalize_status("resolved") == "Resolved"
    assert normalize_status("RESOLVED") == "Resolved"
    assert normalize_status("invalid_banana_status") is None


def test_allowed_lifecycle_transitions():
    # Initial: Reported -> Under Review
    assert is_valid_transition("Reported", "Under Review") is True

    # Under Review -> In Progress
    assert is_valid_transition("Under Review", "In Progress") is True

    # Under Review -> Resolved
    assert is_valid_transition("Under Review", "Resolved") is True

    # In Progress -> Resolved
    assert is_valid_transition("In Progress", "Resolved") is True

    # In Progress -> Under Review (re-evaluation)
    assert is_valid_transition("In Progress", "Under Review") is True

    # Resolved -> In Progress (re-opened)
    assert is_valid_transition("Resolved", "In Progress") is True

    # Same status transition (no-op)
    assert is_valid_transition("In Progress", "In Progress") is True


def test_forbidden_lifecycle_transitions():
    # Direct jump from Reported to Resolved is forbidden without review
    assert is_valid_transition("Reported", "Resolved") is False

    # Direct jump from Reported to In Progress is forbidden without triage
    assert is_valid_transition("Reported", "In Progress") is False

    # Jump from Resolved to Under Review is forbidden (must re-open as In Progress)
    assert is_valid_transition("Resolved", "Under Review") is False

    # Jump from Resolved to Reported is forbidden
    assert is_valid_transition("Resolved", "Reported") is False


def test_create_history_entry():
    entry = create_history_entry(
        status="Under Review",
        actor="coordinator_1",
        notes="Reviewing reports.",
        timestamp_iso="2026-11-15T12:00:00Z",
    )
    assert entry["status"] == "Under Review"
    assert entry["actor"] == "coordinator_1"
    assert entry["notes"] == "Reviewing reports."
    assert entry["timestamp"] == "2026-11-15T12:00:00Z"
