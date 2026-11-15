"""GET /incidents/{id} — retrieve a single incident with a presigned photo URL."""

from shared.config import TABLE_NAME, PHOTO_BUCKET, PRESIGNED_URL_EXPIRY_SEC
from shared.response import error, success

try:
    import boto3
    dynamodb = boto3.resource("dynamodb")
    table = dynamodb.Table(TABLE_NAME)
    s3 = boto3.client("s3")
except Exception:
    boto3 = None
    dynamodb = None
    table = None
    s3 = None


def handler(event, context):
    incident_id = (event.get("pathParameters") or {}).get("id")
    if not incident_id:
        return error("Missing incident ID in path", 400)

    if table is None:
        return error("Database not configured", 500)

    try:
        result = table.get_item(Key={"incidentId": incident_id})
    except Exception as exc:
        return error(f"DynamoDB error: {exc}", 500)

    item = result.get("Item")
    if not item:
        return error("Incident not found", 404)

    # Attach a short-lived presigned GET URL for the photo
    photo_key = item.get("photoKey")
    if photo_key and s3 is not None:
        try:
            item["photoUrl"] = s3.generate_presigned_url(
                "get_object",
                Params={"Bucket": PHOTO_BUCKET, "Key": photo_key},
                ExpiresIn=PRESIGNED_URL_EXPIRY_SEC,
            )
        except Exception:
            item["photoUrl"] = None

    return success({"incident": item})
