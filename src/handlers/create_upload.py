"""POST /uploads — generate a short-lived presigned S3 PUT URL."""

import json
import uuid

from shared.config import (
    PHOTO_BUCKET,
    MAX_IMAGE_SIZE_BYTES,
    PRESIGNED_URL_EXPIRY_SEC,
)
from shared.response import error, success
from shared.validators import validate_upload

try:
    import boto3
    s3 = boto3.client("s3")
except Exception:
    boto3 = None
    s3 = None


def handler(event, context):
    try:
        body = json.loads(event.get("body") or "{}")
    except (json.JSONDecodeError, TypeError):
        return error("Invalid JSON body", 400)

    errors = validate_upload(body)
    if errors:
        return error("; ".join(errors), 400)

    content_type = body["contentType"]
    filename = body["filename"]
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "jpg"
    key = f"uploads/{uuid.uuid4()}.{ext}"

    if s3 is not None:
        try:
            presigned_url = s3.generate_presigned_url(
                "put_object",
                Params={
                    "Bucket": PHOTO_BUCKET,
                    "Key": key,
                    "ContentType": content_type,
                },
                ExpiresIn=PRESIGNED_URL_EXPIRY_SEC,
                HttpMethod="PUT",
            )
        except Exception as exc:
            return error(f"Failed to generate upload URL: {exc}", 500)
    else:
        presigned_url = f"https://{PHOTO_BUCKET}.s3.amazonaws.com/{key}?mock-presigned=true"

    return success(
        {
            "uploadUrl": presigned_url,
            "photoKey": key,
            "expiresIn": PRESIGNED_URL_EXPIRY_SEC,
            "maxSizeBytes": MAX_IMAGE_SIZE_BYTES,
            "contentType": content_type,
        },
        status_code=201,
    )
