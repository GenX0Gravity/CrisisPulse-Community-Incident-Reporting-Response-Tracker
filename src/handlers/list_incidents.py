"""GET /incidents — paginated listing sorted by createdAt (newest first)."""

import base64
import json

from shared.config import TABLE_NAME, ENTITY_TYPE, CREATED_AT_INDEX
from shared.response import error, success

try:
    import boto3
    from boto3.dynamodb.conditions import Key
    dynamodb = boto3.resource("dynamodb")
    table = dynamodb.Table(TABLE_NAME)
except Exception:
    boto3 = None
    Key = None
    dynamodb = None
    table = None


def handler(event, context):
    params = event.get("queryStringParameters") or {}

    try:
        limit = min(int(params.get("limit", "20")), 100)
    except ValueError:
        return error("limit must be an integer", 400)

    order = params.get("order", "desc")
    scan_forward = order != "desc"

    if table is None:
        return success({"incidents": [], "count": 0})

    query_params = {
        "IndexName": CREATED_AT_INDEX,
        "KeyConditionExpression": Key("entityType").eq(ENTITY_TYPE),
        "ScanIndexForward": scan_forward,
        "Limit": limit,
    }

    cursor = params.get("cursor")
    if cursor:
        try:
            last_key = json.loads(base64.b64decode(cursor))
            query_params["ExclusiveStartKey"] = last_key
        except Exception:
            return error("Invalid cursor value", 400)

    try:
        result = table.query(**query_params)
    except Exception as exc:
        return error(f"Query failed: {exc}", 500)

    items = result.get("Items", [])
    body: dict = {
        "incidents": items,
        "count": len(items),
    }

    if "LastEvaluatedKey" in result:
        body["nextCursor"] = base64.b64encode(
            json.dumps(result["LastEvaluatedKey"], default=str).encode()
        ).decode()

    return success(body)
