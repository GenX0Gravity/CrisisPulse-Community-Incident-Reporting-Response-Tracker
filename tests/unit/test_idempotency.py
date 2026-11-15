"""Unit tests for submission idempotency."""

import os
import sys
from unittest.mock import MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

from shared.idempotency import (
    extract_idempotency_key,
    get_existing_idempotent_incident,
    record_idempotency_key,
)


def test_extract_idempotency_key_from_header():
    event = {"headers": {"Idempotency-Key": "my-client-key-123"}}
    body = {}
    key = extract_idempotency_key(event, body)
    assert key == "my-client-key-123"


def test_extract_idempotency_key_case_insensitive():
    event = {"headers": {"x-idempotency-key": "alt-header-key-456"}}
    body = {}
    key = extract_idempotency_key(event, body)
    assert key == "alt-header-key-456"


def test_extract_idempotency_key_from_body():
    event = {"headers": {}}
    body = {"idempotencyKey": "body-key-789"}
    key = extract_idempotency_key(event, body)
    assert key == "body-key-789"


def test_get_existing_idempotent_incident():
    mock_table = MagicMock()
    # Step 1: IDEMP# record
    mock_table.get_item.side_effect = [
        {"Item": {"incidentId": "IDEMP#key-1", "targetIncidentId": "incident-abc-123"}},
        {"Item": {"incidentId": "incident-abc-123", "title": "Existing Incident", "status": "triaged"}},
    ]

    item = get_existing_idempotent_incident(mock_table, "key-1")
    assert item is not None
    assert item["incidentId"] == "incident-abc-123"
    assert item["status"] == "triaged"


def test_get_existing_idempotent_incident_missing():
    mock_table = MagicMock()
    mock_table.get_item.return_value = {}  # Not found
    item = get_existing_idempotent_incident(mock_table, "non-existent-key")
    assert item is None


def test_record_idempotency_key_success():
    mock_table = MagicMock()
    mock_table.put_item.return_value = {}
    success = record_idempotency_key(mock_table, "key-1", "incident-abc-123")
    assert success is True
    mock_table.put_item.assert_called_once()
