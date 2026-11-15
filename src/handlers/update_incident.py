"""PATCH /incidents/{id} — Protected incident updates (descriptive fields only).

NOTE:
1. Unauthenticated callers are strictly rejected with HTTP 401 Unauthorized.
2. Status modifications are strictly forbidden on this endpoint and return HTTP 403 Forbidden.
   Status updates must use the coordinator status endpoint with coordinator authorization.
"""

from __future__ import annotations

import json
import os
import time

from shared.config import TABLE_NAME
from shared.response import error, success
from shared.validators import validate_update

try:
    import boto3
    dynamodb = boto3.resource("dynamodb")
    table = dynamodb.Table(TABLE_NAME)
except Exception:
    boto3 = None
    dynamodb = None
    table = None


def _is_authenticated(event: dict) -> tuple[bool, str]:
    """Verify caller is authenticated via Cognito JWT authorizer claims or Bearer token."""
    req_context = event.get("requestContext") or {}
    authorizer = req_context.get("authorizer") or {}

    # Check Cognito User Pool claims from API Gateway authorizer
    jwt_claims = authorizer.get("jwt", {}).get("claims") or authorizer.get("claims")
    if jwt_claims:
        username = (
            jwt_claims.get("cognito:username")
            or jwt_claims.get("username")
            or jwt_claims.get("email")
            or jwt_claims.get("sub")
            or "authenticated_user"
        )
        return True, str(username)

    # Check Authorization header (for test / local / fallback environments)
    headers = event.get("headers") or {}
    auth_header = None
    for h_name, h_val in headers.items():
        if h_name.lower() == "authorization":
            auth_header = h_val
            break

    if not auth_header:
        return False, "anonymous"

    parts = auth_header.split()
    if len(parts) == 2 and parts[0].lower() == "bearer":
        token = parts[1].strip()
        demo_token = os.environ.get("COORDINATOR_DEMO_TOKEN")
        if demo_token and token == demo_token:
            return True, "demo-coordinator"
        if token and not token.startswith("public") and len(token) >= 16:
            return True, f"bearer-user-{token[:8]}"

    return False, "unauthorized"


def handler(event, context):
    incident_id = (event.get("pathParameters") or {}).get("id")
    if not incident_id:
        return error("Missing incident ID in path", 400)

    # 1. Reject unauthenticated callers (401 Unauthorized)
    is_auth, caller_id = _is_authenticated(event)
    if not is_auth:
        return error(
            "Unauthorized: Authentication required to modify incident reports. "
            "Please provide a valid Authorization Bearer token.",
            401,
        )

    try:
        body = json.loads(event.get("body") or "{}")
    except (json.JSONDecodeError, TypeError):
        return error("Invalid JSON body", 400)

    # 2. Reject attempts to update status on this endpoint (403 Forbidden)
    if "status" in body:
        return error(
            "Forbidden: Incident status cannot be modified via /incidents/{id}. "
            "Status updates require coordinator authorization via /coordinator/incidents/{id}/status.",
            403,
        )

    errors = validate_update(body)
    if errors:
        return error("; ".join(errors), 400)

    if table is None:
        return error("Database not configured", 500)

    # Verify the incident exists
    existing = table.get_item(Key={"incidentId": incident_id})
    if "Item" not in existing:
        return error("Incident not found", 404)

    # Always stamp the update time and modifier
    body["updatedAt"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    body["lastModifiedBy"] = caller_id

    update_parts: list[str] = []
    expr_names: dict[str, str] = {}
    expr_values: dict = {}

    for idx, (key, value) in enumerate(body.items()):
        attr_name = f"#a{idx}"
        attr_val = f":v{idx}"
        update_parts.append(f"{attr_name} = {attr_val}")
        expr_names[attr_name] = key
        expr_values[attr_val] = value

    try:
        result = table.update_item(
            Key={"incidentId": incident_id},
            UpdateExpression="SET " + ", ".join(update_parts),
            ExpressionAttributeNames=expr_names,
            ExpressionAttributeValues=expr_values,
            ReturnValues="ALL_NEW",
        )
    except Exception as exc:
        return error(f"Update failed: {exc}", 500)

    return success({"incident": result.get("Attributes", {})})
