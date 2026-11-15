"""PATCH /incidents/{id} — Public incident updates (descriptive fields only).

NOTE: Public users are strictly forbidden from modifying lifecycle 'status'.
Status modifications must use the coordinator status endpoint with authorization.
"""

import json
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


def handler(event, context):
    incident_id = (event.get("pathParameters") or {}).get("id")
    if not incident_id:
        return error("Missing incident ID in path", 400)

    try:
        body = json.loads(event.get("body") or "{}")
    except (json.JSONDecodeError, TypeError):
        return error("Invalid JSON body", 400)

    # Reject attempts to update status on public endpoint
    if "status" in body:
        return error(
            "Public users are not permitted to modify incident status. "
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

    # Always stamp the update time
    body["updatedAt"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

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
