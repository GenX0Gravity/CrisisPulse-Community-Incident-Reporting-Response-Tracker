"""POST /incidents — create a new incident report, ensure idempotency, and trigger workflow."""

from __future__ import annotations

import json
import time
import uuid
from decimal import Decimal

from shared.config import TABLE_NAME, ENTITY_TYPE, STATE_MACHINE_ARN
from shared.idempotency import (
    extract_idempotency_key,
    get_existing_idempotent_incident,
    record_idempotency_key,
)
from shared.lifecycle import create_history_entry
from shared.response import error, success
from shared.scoring import calculate_priority_score
from shared.validators import validate_incident_submission

try:
    import boto3
    dynamodb = boto3.resource("dynamodb")
    table = dynamodb.Table(TABLE_NAME)
    sfn = boto3.client("stepfunctions")
except Exception:
    boto3 = None
    dynamodb = None
    table = None
    sfn = None


def handler(event, context):
    try:
        body = json.loads(event.get("body") or "{}")
    except (json.JSONDecodeError, TypeError):
        return error("Invalid JSON body in request", 400)

    # 1. Strict Input Validation
    validation_errors = validate_incident_submission(body)
    if validation_errors:
        return error("; ".join(validation_errors), 400)

    # 2. Idempotency Check
    idemp_key = extract_idempotency_key(event, body)
    if idemp_key and table is not None:
        existing_incident = get_existing_idempotent_incident(table, idemp_key)
        if existing_incident:
            # Return existing incident directly; do not create duplicate
            return success(
                {
                    "incident": existing_incident,
                    "idempotentReplay": True,
                    "message": "Returned existing incident matching idempotency key.",
                },
                status_code=200,
            )

    # 3. Server-side Incident ID Generation & Timestamps
    incident_id = str(uuid.uuid4())
    now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    category = body["category"].strip().lower()
    description = body["description"].strip()
    approx_loc = (
        body.get("approximateLocation") or body.get("approximate_location") or ""
    ).strip()
    photo_key = body.get("photoKey") or body.get("s3Key") or ""
    risk_factors = body.get("riskFactors") or []
    reporter = body.get("reporterName") or "Anonymous"

    # Pre-calculate initial deterministic priority score
    scoring_result = calculate_priority_score(category, risk_factors)

    # Initial status history record
    initial_history = [
        create_history_entry(
            status="Reported",
            actor=reporter if reporter != "Anonymous" else "public_user",
            notes="Initial incident submission received via API Gateway.",
            timestamp_iso=now_iso,
        )
    ]

    # 4. Assemble DynamoDB Item
    item: dict = {
        "incidentId": incident_id,
        "entityType": ENTITY_TYPE,
        "category": category,
        "description": description,
        "approximateLocation": approx_loc,
        "reporterName": reporter,
        "photoKey": photo_key,
        "riskFactors": risk_factors,
        "status": "Reported",
        "statusHistory": initial_history,
        "priority": scoring_result["priority"],
        "priorityScore": Decimal(str(scoring_result["score"])),
        "priorityExplanation": scoring_result["explanation"],
        "isPotentialDuplicate": False,
        "createdAt": now_iso,
        "updatedAt": now_iso,
        "workflowMetadata": {
            "state": "STARTED",
            "triggeredAt": now_iso,
        },
    }

    # Optional coordinates
    lat = body.get("latitude")
    lon = body.get("longitude")
    if lat is not None and lon is not None:
        item["latitude"] = Decimal(str(lat))
        item["longitude"] = Decimal(str(lon))

    # Optional idempotency key tracking on item
    if idemp_key:
        item["idempotencyKey"] = idemp_key

    # 5. Persist Incident to DynamoDB
    if table is not None:
        try:
            table.put_item(
                Item=item,
                ConditionExpression="attribute_not_exists(incidentId)",
            )
        except Exception as exc:
            return error(f"Failed to persist incident: {exc}", 500)

        # 6. Record Idempotency Mapping
        if idemp_key:
            record_idempotency_key(table, idemp_key, incident_id)

    # 7. Start Step Functions Workflow
    if STATE_MACHINE_ARN and sfn is not None:
        try:
            workflow_input = {
                "incidentId": incident_id,
                "category": category,
                "description": description,
                "approximateLocation": approx_loc,
                "photoKey": photo_key,
                "riskFactors": risk_factors,
                "createdAt": now_iso,
            }
            if lat is not None and lon is not None:
                workflow_input["latitude"] = float(lat)
                workflow_input["longitude"] = float(lon)

            sfn.start_execution(
                stateMachineArn=STATE_MACHINE_ARN,
                name=f"incident-{incident_id}",
                input=json.dumps(workflow_input),
            )
        except Exception as exc:
            item["workflowMetadata"]["state"] = "TRIGGER_FAILED"
            item["workflowMetadata"]["error"] = str(exc)

    return success(
        {
            "incidentId": incident_id,
            "status": item["status"],
            "priority": item["priority"],
            "createdAt": item["createdAt"],
            "incident": item,
        },
        status_code=201,
    )
