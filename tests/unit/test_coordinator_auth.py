"""Unit tests for authorization, Cognito authorizer protection, and public endpoint isolation."""

import json
import os
import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

os.environ.setdefault("TABLE_NAME", "test-incidents")
os.environ.setdefault("PHOTO_BUCKET", "test-photos")
os.environ.setdefault("DEMO_MODE", "true")
os.environ.setdefault("FRONTEND_ORIGIN", "http://localhost:3000")
os.environ.setdefault("COORDINATOR_DEMO_TOKEN", "demo-coordinator-secret-key-2026")

from handlers.coordinator_update_status import handler as coordinator_handler
from handlers.health import handler as health_handler
from handlers.list_incidents import handler as list_incidents_handler
from handlers.update_incident import handler as update_incident_handler


# ══════════════════════════════════════════════════════════════════════
# 1. Protection Against Unauthorized Public Writes (HTTP 401 / 403)
# ══════════════════════════════════════════════════════════════════════

def test_unauthenticated_patch_incident_returns_401():
    """Verify unauthenticated callers to PATCH /incidents/{id} receive HTTP 401 Unauthorized."""
    event = {
        "pathParameters": {"id": "inc-unauth-001"},
        "headers": {},  # No credentials
        "requestContext": {},
        "body": json.dumps({"description": "Updated description attempt by anonymous caller"}),
    }
    result = update_incident_handler(event, None)
    assert result["statusCode"] == 401, f"Expected 401, got {result['statusCode']}"
    body = json.loads(result["body"])
    assert "Authentication required" in body["error"]


def test_unauthenticated_coordinator_status_returns_401():
    """Verify unauthenticated callers to POST /coordinator/incidents/{id}/status receive HTTP 401."""
    event = {
        "pathParameters": {"id": "inc-coord-001"},
        "headers": {},  # No authorization header
        "requestContext": {},  # No authorizer context
        "body": json.dumps({"status": "In Progress"}),
    }
    result = coordinator_handler(event, None)
    assert result["statusCode"] == 401, f"Expected 401, got {result['statusCode']}"
    body = json.loads(result["body"])
    assert "Coordinator authorization required" in body["error"]


def test_coordinator_endpoint_rejects_public_token():
    """Verify coordinator endpoint rejects unprivileged public tokens with HTTP 401."""
    event = {
        "pathParameters": {"id": "inc-coord-001"},
        "headers": {"Authorization": "Bearer public-user-token-123"},
        "requestContext": {},
        "body": json.dumps({"status": "In Progress"}),
    }
    result = coordinator_handler(event, None)
    assert result["statusCode"] == 401
    body = json.loads(result["body"])
    assert "Coordinator authorization required" in body["error"]


def test_coordinator_endpoint_rejects_arbitrary_string_token():
    """Verify coordinator endpoint rejects arbitrary long strings with HTTP 401."""
    event = {
        "pathParameters": {"id": "inc-coord-001"},
        "headers": {"Authorization": "Bearer random-unrecognized-string-999999999"},
        "requestContext": {},
        "body": json.dumps({"status": "In Progress"}),
    }
    result = coordinator_handler(event, None)
    assert result["statusCode"] == 401


def test_patch_incident_rejects_status_modification_with_403():
    """Verify PATCH /incidents/{id} strictly forbids status modifications (HTTP 403 Forbidden)."""
    # Even when caller is authenticated, status cannot be updated via PATCH /incidents/{id}
    event = {
        "pathParameters": {"id": "inc-public-001"},
        "headers": {"Authorization": "Bearer coordinator-valid-jwt-token"},
        "requestContext": {
            "authorizer": {
                "jwt": {
                    "claims": {"cognito:username": "test_user_01"}
                }
            }
        },
        "body": json.dumps({"status": "Resolved"}),
    }
    result = update_incident_handler(event, None)
    assert result["statusCode"] == 403, f"Expected 403, got {result['statusCode']}"
    body = json.loads(result["body"])
    assert "Forbidden" in body["error"] or "not permitted to modify incident status" in body["error"]


# ══════════════════════════════════════════════════════════════════════
# 2. Authorized Writes (Cognito JWT & Coordinator Tokens)
# ══════════════════════════════════════════════════════════════════════

@patch("handlers.update_incident.table")
def test_authenticated_patch_incident_descriptive_success(mock_table):
    """Verify authenticated caller can update descriptive fields on an existing incident."""
    mock_table.get_item.return_value = {
        "Item": {
            "incidentId": "inc-auth-001",
            "category": "utility",
            "description": "Original description",
            "status": "Reported",
        }
    }
    mock_table.update_item.return_value = {
        "Attributes": {
            "incidentId": "inc-auth-001",
            "description": "Updated by authenticated coordinator",
            "lastModifiedBy": "chief_coordinator",
        }
    }

    event = {
        "pathParameters": {"id": "inc-auth-001"},
        "requestContext": {
            "authorizer": {
                "jwt": {
                    "claims": {
                        "cognito:username": "chief_coordinator",
                        "email": "chief@emergency.gov",
                    }
                }
            }
        },
        "body": json.dumps({"description": "Updated by authenticated coordinator"}),
    }

    result = update_incident_handler(event, None)
    assert result["statusCode"] == 200, f"Expected 200, got {result['statusCode']}: {result.get('body')}"
    body = json.loads(result["body"])
    assert body["incident"]["description"] == "Updated by authenticated coordinator"


@patch("handlers.coordinator_update_status.table")
def test_coordinator_authorized_cognito_claims_success(mock_table):
    """Verify authorized coordinator with Cognito claims can transition status and record history."""
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
def test_coordinator_authorized_demo_bearer_token_success(mock_table):
    """Verify authorized coordinator with configured demo token can transition status."""
    mock_table.get_item.return_value = {
        "Item": {
            "incidentId": "inc-coord-002",
            "status": "Under Review",
            "statusHistory": [],
        }
    }
    mock_table.update_item.return_value = {
        "Attributes": {
            "incidentId": "inc-coord-002",
            "status": "In Progress",
        }
    }

    event = {
        "pathParameters": {"id": "inc-coord-002"},
        "headers": {
            "Authorization": "Bearer demo-coordinator-secret-key-2026"
        },
        "body": json.dumps({
            "status": "In Progress",
            "notes": "Dispatching emergency field team.",
        }),
    }

    result = coordinator_handler(event, None)
    assert result["statusCode"] == 200
    body = json.loads(result["body"])
    assert body["transition"]["currentStatus"] == "In Progress"
    assert body["transition"]["actor"] == "demo-coordinator"


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
            "Authorization": "Bearer coordinator-valid-jwt-token-abcdef"
        },
        "body": json.dumps({"status": "Resolved"}),  # Illegal direct jump!
    }

    result = coordinator_handler(event, None)
    assert result["statusCode"] == 400
    body = json.loads(result["body"])
    assert "Illegal status transition" in body["error"]


# ══════════════════════════════════════════════════════════════════════
# 3. Public Endpoints Remain Open Without Authentication
# ══════════════════════════════════════════════════════════════════════

def test_public_health_endpoint_requires_no_auth():
    """Verify GET /health remains publicly accessible without credentials."""
    event = {
        "headers": {},
        "requestContext": {},
    }
    result = health_handler(event, None)
    assert result["statusCode"] == 200
    body = json.loads(result["body"])
    assert body["status"] == "healthy"


@patch("handlers.list_incidents.table")
def test_public_list_incidents_requires_no_auth(mock_table):
    """Verify GET /incidents remains publicly accessible without credentials."""
    mock_table.query.return_value = {
        "Items": [
            {
                "incidentId": "inc-open-001",
                "category": "infrastructure",
                "createdAt": "2026-11-15T12:00:00Z",
                "status": "Reported",
            }
        ]
    }
    event = {
        "headers": {},
        "requestContext": {},
        "queryStringParameters": {},
    }
    result = list_incidents_handler(event, None)
    assert result["statusCode"] == 200
    body = json.loads(result["body"])
    assert len(body["incidents"]) == 1
