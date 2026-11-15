"""Unit tests for unauthorized requests, public restrictions, and coordinator endpoints."""

import json
import os
import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

os.environ.setdefault("TABLE_NAME", "test-incidents")
os.environ.setdefault("PHOTO_BUCKET", "test-photos")
os.environ.setdefault("DEMO_MODE", "true")
os.environ.setdefault("FRONTEND_ORIGIN", "http://localhost:3000")

from handlers.update_incident import handler as public_update_handler
from handlers.coordinator_update_status import handler as coordinator_handler


def test_public_update_rejects_status_modification():
    """Verify public PATCH /incidents/{id} rejects any attempt to update status (403 Forbidden)."""
    event = {
        "pathParameters": {"id": "inc-public-001"},
        "body": json.dumps({"status": "Resolved"}),
    }
    result = public_update_handler(event, None)
    assert result["statusCode"] == 403
    body = json.loads(result["body"])
    assert "not permitted to modify incident status" in body["error"]


def test_coordinator_endpoint_rejects_unauthorized_request():
    """Verify coordinator status endpoint rejects requests without credentials (401 Unauthorized)."""
    event = {
        "pathParameters": {"id": "inc-coord-001"},
        "headers": {},  # No authorization header
        "requestContext": {},  # No authorizer context
        "body": json.dumps({"status": "In Progress"}),
    }
    result = coordinator_handler(event, None)
    assert result["statusCode"] == 401
    body = json.loads(result["body"])
    assert "Coordinator authorization required" in body["error"]


def test_coordinator_endpoint_rejects_public_token():
    """Verify coordinator endpoint rejects unprivileged public tokens."""
    event = {
        "pathParameters": {"id": "inc-coord-001"},
        "headers": {"Authorization": "Bearer public-user-token-123"},
        "body": json.dumps({"status": "In Progress"}),
    }
    result = coordinator_handler(event, None)
    assert result["statusCode"] == 401


@patch("handlers.coordinator_update_status.table")
def test_coordinator_authorized_cognito_claims_success(mock_table):
    """Verify authorized coordinator with Cognito claims can transition status and record history."""
    # Mock existing incident currently in 'Reported'
    mock_table.get_item.return_value = {
        "Item": {
            "incidentId": "inc-coord-001",
            "status": "Reported",
            "statusHistory": [
                {
                    "status": "Reported",
                    "timestamp": "2026-11-15T10:00:00Z",
                    "actor": "reporter",
                }
            ],
        }
    }
    mock_table.update_item.return_value = {
        "Attributes": {
            "incidentId": "inc-coord-001",
            "status": "Under Review",
        }
    }

    event = {
        "pathParameters": {"id": "inc-coord-001"},
        "requestContext": {
            "authorizer": {
                "jwt": {
                    "claims": {
                        "cognito:username": "coord_chief_99",
                        "email": "coordinator@example.gov",
                    }
                }
            }
        },
        "body": json.dumps({
            "status": "Under Review",
            "notes": "Coordinator reviewing site assessment.",
        }),
    }

    result = coordinator_handler(event, None)
    assert result["statusCode"] == 200
    body = json.loads(result["body"])
    assert body["transition"]["previousStatus"] == "Reported"
    assert body["transition"]["currentStatus"] == "Under Review"
    assert body["transition"]["actor"] == "coord_chief_99"


@patch("handlers.coordinator_update_status.table")
def test_coordinator_rejects_illegal_lifecycle_jump(mock_table):
    """Verify coordinator endpoint enforces lifecycle rules (Reported -> Resolved is forbidden)."""
    mock_table.get_item.return_value = {
        "Item": {
            "incidentId": "inc-coord-001",
            "status": "Reported",
        }
    }

    event = {
        "pathParameters": {"id": "inc-coord-001"},
        "headers": {
            # Valid 32+ char bearer token for test
            "Authorization": "Bearer coordinator-valid-jwt-token-abcdef1234567890"
        },
        "body": json.dumps({"status": "Resolved"}),  # Illegal direct jump!
    }

    result = coordinator_handler(event, None)
    assert result["statusCode"] == 400
    body = json.loads(result["body"])
    assert "Illegal status transition" in body["error"]
