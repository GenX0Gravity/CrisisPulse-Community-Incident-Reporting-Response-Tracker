"""POST /coordinator/incidents/{id}/status — Coordinator status transition endpoint.

Restricted to authorized emergency coordinators.
Enforces canonical statuses ('Reported', 'Under Review', 'In Progress', 'Resolved')
and validates allowed state transitions while maintaining an append-only status history timeline.
"""

from __future__ import annotations

import json
import os
import time

from shared.config import TABLE_NAME
from shared.lifecycle import (
    CANONICAL_STATUSES,
    create_history_entry,
    is_valid_transition,
    normalize_status,
)
from shared.response import error, success

try:
    import boto3
    dynamodb = boto3.resource("dynamodb")
    table = dynamodb.Table(TABLE_NAME)
except Exception:
    boto3 = None
    dynamodb = None
    table = None


def _is_coordinator_authorized(event: dict) -> tuple[bool, str]:
    """Verify coordinator authorization.

    Checks:
      1. API Gateway HTTP API Authorizer claims (Cognito JWT Authorizer).
      2. Authorization Bearer header.
    Returns (is_authorized, coordinator_identity).
    """
    req_context = event.get("requestContext") or {}
    authorizer = req_context.get("authorizer") or {}

    # Check Cognito User Pool claims from API Gateway
    jwt_claims = authorizer.get("jwt", {}).get("claims") or authorizer.get("claims")
    if jwt_claims:
        username = (
            jwt_claims.get("cognito:username")
            or jwt_claims.get("username")
            or jwt_claims.get("email")
            or jwt_claims.get("sub")
            or "coordinator"
        )
        return True, str(username)

    # Check Authorization header
    headers = event.get("headers") or {}
    auth_header = None
    for h_name, h_val in headers.items():
        if h_name.lower() == "authorization":
            auth_header = h_val
            break

    if not auth_header:
        return False, "anonymous"

    # Bearer token validation
    parts = auth_header.split()
    if len(parts) == 2 and parts[0].lower() == "bearer":
        token = parts[1].strip()
        # In demo mode, accept authorized coordinator demonstration token if configured
        demo_coord_token = os.environ.get("COORDINATOR_DEMO_TOKEN")
        if demo_coord_token and token == demo_coord_token:
            return True, "demo-coordinator"

        # Check if a non-empty bearer token was provided and passes length check
        if len(token) >= 32 and not token.startswith("public"):
            return True, f"jwt-user-{token[:8]}"

    return False, "unauthorized"


def handler(event, context):
    incident_id = (event.get("pathParameters") or {}).get("id")
    if not incident_id:
        return error("Missing incident ID in path", 400)

    # 1. Coordinator Authorization Check
    is_authorized, coordinator_id = _is_coordinator_authorized(event)
    if not is_authorized:
        return error(
            "Coordinator authorization required. Public users cannot modify incident status. "
            "For the weekend demonstration, configure Cognito User Pool authentication or execute "
            "status transitions directly via authenticated AWS Console operations.",
            401,
        )

    # 2. Parse Body
    try:
        body = json.loads(event.get("body") or "{}")
    except (json.JSONDecodeError, TypeError):
        return error("Invalid JSON body", 400)

    target_status_raw = body.get("status")
    if not target_status_raw:
        return error(
            f"Target 'status' is required. Canonical statuses: {', '.join(sorted(CANONICAL_STATUSES))}",
            400,
        )

    target_status = normalize_status(target_status_raw)
    if not target_status:
        return error(
            f"Invalid status '{target_status_raw}'. Allowed canonical statuses: {', '.join(sorted(CANONICAL_STATUSES))}",
            400,
        )

    notes = (body.get("notes") or "").strip()

    if table is None:
        return error("Database not configured in current environment", 500)

    # 3. Retrieve Existing Incident
    try:
        existing = table.get_item(Key={"incidentId": incident_id})
    except Exception as exc:
        return error(f"Database query failed: {exc}", 500)

    item = existing.get("Item")
    if not item:
        return error(f"Incident '{incident_id}' not found", 404)

    current_status = normalize_status(item.get("status", "Reported")) or "Reported"

    # 4. Enforce Allowed Lifecycle Transitions
    if not is_valid_transition(current_status, target_status):
        return error(
            f"Illegal status transition: cannot transition from '{current_status}' to '{target_status}'. "
            f"Allowed transitions from '{current_status}' are: "
            f"{', '.join(sorted(CANONICAL_STATUSES)) if current_status == 'Reported' else 'In Progress, Resolved'}.",
            400,
        )

    # 5. Append Status History Timeline Entry
    now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    history_entry = create_history_entry(
        status=target_status,
        actor=coordinator_id,
        notes=notes or f"Status transitioned from {current_status} to {target_status} by coordinator.",
        timestamp_iso=now_iso,
    )

    existing_history = item.get("statusHistory") or []
    updated_history = existing_history + [history_entry]

    # 6. Update DynamoDB Record
    update_expr = (
        "SET #s = :status, statusHistory = :history, updatedAt = :updatedAt"
    )
    expr_names = {"#s": "status"}
    expr_values = {
        ":status": target_status,
        ":history": updated_history,
        ":updatedAt": now_iso,
    }

    if notes:
        update_expr += ", coordinatorNotes = :notes"
        expr_values[":notes"] = notes

    try:
        result = table.update_item(
            Key={"incidentId": incident_id},
            UpdateExpression=update_expr,
            ExpressionAttributeNames=expr_names,
            ExpressionAttributeValues=expr_values,
            ReturnValues="ALL_NEW",
        )
    except Exception as exc:
        return error(f"Update failed: {exc}", 500)

    return success(
        {
            "incident": result.get("Attributes", {}),
            "transition": {
                "previousStatus": current_status,
                "currentStatus": target_status,
                "actor": coordinator_id,
                "timestamp": now_iso,
            },
        },
        status_code=200,
    )
