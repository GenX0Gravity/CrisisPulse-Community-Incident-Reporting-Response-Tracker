"""Input validation for CrisisPulse API requests."""

from __future__ import annotations

import re

from shared.config import ALLOWED_CONTENT_TYPES
from shared.lifecycle import CANONICAL_STATUSES, normalize_status
from shared.scoring import RISK_FACTOR_WEIGHTS

VALID_SEVERITIES = {"low", "medium", "high", "critical", "unclassified"}

VALID_CATEGORIES = {
    "fire",
    "flood",
    "accident",
    "crime",
    "infrastructure",
    "medical",
    "hazmat",
    "weather",
    "environmental",
    "other",
}

S3_KEY_REGEX = re.compile(r"^uploads/[\w\-. ]+$")
IDEMPOTENCY_KEY_REGEX = re.compile(r"^[A-Za-z0-9_\-:.]{1,128}$")


def validate_incident_submission(data: dict) -> list[str]:
    """Validate incident submission payload.

    Accepts:
        - category (required)
        - description (required)
        - approximateLocation (required)
        - latitude & longitude (optional; if one is provided, both must be valid)
        - photoKey / s3Key (optional uploaded S3 object key)
        - riskFactors (optional list of recognized risk factors)
        - idempotencyKey (optional client-provided unique key)
    """
    errors: list[str] = []

    if not isinstance(data, dict):
        return ["Request payload must be a JSON object"]

    # 1. category (required)
    category = data.get("category")
    if not category or not isinstance(category, str):
        errors.append("category is required and must be a string")
    elif category.strip().lower() not in VALID_CATEGORIES:
        errors.append(
            f"category must be one of: {', '.join(sorted(VALID_CATEGORIES))}"
        )

    # 2. description (required)
    desc = data.get("description")
    if not desc or not isinstance(desc, str):
        errors.append("description is required and must be a non-empty string")
    elif len(desc.strip()) < 5:
        errors.append("description must be at least 5 characters long")
    elif len(desc) > 2000:
        errors.append("description must be 2000 characters or fewer")

    # 3. approximateLocation (required)
    approx_loc = data.get("approximateLocation") or data.get("approximate_location")
    if not approx_loc or not isinstance(approx_loc, str):
        errors.append(
            "approximateLocation is required and must be a non-empty string"
        )
    elif len(approx_loc.strip()) < 2:
        errors.append("approximateLocation must be at least 2 characters long")
    elif len(approx_loc) > 250:
        errors.append("approximateLocation must be 250 characters or fewer")

    # 4. Optional latitude & longitude
    lat = data.get("latitude")
    lon = data.get("longitude")

    if lat is not None or lon is not None:
        if lat is None or lon is None:
            errors.append(
                "Both latitude and longitude must be provided when specifying coordinates"
            )
        else:
            if not isinstance(lat, (int, float)):
                errors.append("latitude must be a numeric value")
            elif not (-90.0 <= lat <= 90.0):
                errors.append("latitude must be between -90 and 90 degrees")

            if not isinstance(lon, (int, float)):
                errors.append("longitude must be a numeric value")
            elif not (-180.0 <= lon <= 180.0):
                errors.append("longitude must be between -180 and 180 degrees")

    # 5. Optional photoKey / s3Key
    photo_key = data.get("photoKey") or data.get("s3Key")
    if photo_key is not None:
        if not isinstance(photo_key, str) or not S3_KEY_REGEX.match(photo_key):
            errors.append(
                "photoKey must be a valid uploaded object key in the 'uploads/' directory"
            )

    # 6. Optional riskFactors
    risk_factors = data.get("riskFactors")
    if risk_factors is not None:
        if not isinstance(risk_factors, list):
            errors.append("riskFactors must be an array of strings")
        else:
            invalid_factors = [
                rf
                for rf in risk_factors
                if not isinstance(rf, str)
                or rf.strip().lower() not in RISK_FACTOR_WEIGHTS
            ]
            if invalid_factors:
                valid_list = ", ".join(sorted(RISK_FACTOR_WEIGHTS.keys()))
                errors.append(
                    f"Unknown risk factors: {invalid_factors}. Recognized factors: {valid_list}"
                )

    # 7. Optional idempotencyKey
    idemp_key = data.get("idempotencyKey")
    if idemp_key is not None:
        if not isinstance(idemp_key, str) or not IDEMPOTENCY_KEY_REGEX.match(
            idemp_key
        ):
            errors.append(
                "idempotencyKey must be an alphanumeric string up to 128 characters"
            )

    # 8. Optional reporterName
    reporter = data.get("reporterName")
    if reporter is not None:
        if not isinstance(reporter, str) or len(reporter) > 100:
            errors.append("reporterName must be a string of 100 characters or fewer")

    return errors


def validate_upload(data: dict) -> list[str]:
    """Validate presigned upload URL request."""
    errors: list[str] = []

    ct = data.get("contentType", "")
    if ct not in ALLOWED_CONTENT_TYPES:
        errors.append(
            f"contentType must be one of: {', '.join(sorted(ALLOWED_CONTENT_TYPES))}"
        )

    fn = data.get("filename", "")
    if not fn or not isinstance(fn, str):
        errors.append("filename is required")
    elif not re.match(r"^[\w\-. ]+$", fn):
        errors.append("filename contains invalid characters")

    return errors


def validate_update(data: dict) -> list[str]:
    """Validate public PATCH incident update request.

    NOTE: Public users are strictly forbidden from modifying lifecycle 'status'.
    Status transitions are protected coordinator actions.
    """
    errors: list[str] = []
    if not data or not isinstance(data, dict):
        errors.append("Request body must contain at least one field to update")
        return errors

    # Enforce that public users cannot modify status
    if "status" in data:
        errors.append(
            "Public users are not permitted to modify incident status. "
            "Status updates require coordinator authorization via the coordinator endpoint."
        )

    allowed = {
        "title",
        "description",
        "category",
        "approximateLocation",
        "latitude",
        "longitude",
    }
    unknown = set(data.keys()) - allowed - {"status"}
    if unknown:
        errors.append(f"Unknown fields: {', '.join(sorted(unknown))}")

    if "category" in data and data["category"].lower() not in VALID_CATEGORIES:
        errors.append(
            f"category must be one of: {', '.join(sorted(VALID_CATEGORIES))}"
        )
    if "description" in data:
        if not isinstance(data["description"], str) or len(data["description"]) > 2000:
            errors.append("description must be a string of 2000 characters or fewer")

    lat = data.get("latitude")
    lon = data.get("longitude")
    if lat is not None and not (-90.0 <= lat <= 90.0):
        errors.append("latitude must be between -90 and 90 degrees")
    if lon is not None and not (-180.0 <= lon <= 180.0):
        errors.append("longitude must be between -180 and 180 degrees")

    return errors
