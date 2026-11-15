"""Unit tests for input validators."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

from shared.validators import (
    validate_incident_submission,
    validate_upload,
    validate_update,
)


def test_valid_incident_submission_minimal():
    data = {
        "category": "fire",
        "description": "Report of dense smoke rising from apartment basement.",
        "approximateLocation": "Elm St & 4th Ave",
    }
    errors = validate_incident_submission(data)
    assert errors == []


def test_valid_incident_submission_with_coordinates_and_risk_factors():
    data = {
        "category": "accident",
        "description": "Two vehicles collided at intersection; traffic blocked.",
        "approximateLocation": "Broad St & High St",
        "latitude": 39.9612,
        "longitude": -82.9988,
        "riskFactors": ["major_road_blocked", "injuries_reported"],
        "photoKey": "uploads/scene-123.jpg",
        "idempotencyKey": "client-key-abc",
        "reporterName": "Citizen Alex",
    }
    errors = validate_incident_submission(data)
    assert errors == []


def test_missing_required_fields():
    data = {}
    errors = validate_incident_submission(data)
    assert any("category" in e for e in errors)
    assert any("description" in e for e in errors)
    assert any("approximateLocation" in e for e in errors)


def test_invalid_category():
    data = {
        "category": "alien_invasion",
        "description": "Spaceship landed.",
        "approximateLocation": "Desert area",
    }
    errors = validate_incident_submission(data)
    assert any("category must be one of" in e for e in errors)


def test_only_one_coordinate_provided():
    data = {
        "category": "medical",
        "description": "Person collapsed near park bench.",
        "approximateLocation": "City Park",
        "latitude": 40.7128,  # Missing longitude
    }
    errors = validate_incident_submission(data)
    assert any("Both latitude and longitude must be provided" in e for e in errors)


def test_coordinates_out_of_bounds():
    data = {
        "category": "medical",
        "description": "Person collapsed near park bench.",
        "approximateLocation": "City Park",
        "latitude": 150.0,  # Invalid (> 90)
        "longitude": -74.0,
    }
    errors = validate_incident_submission(data)
    assert any("latitude must be between -90 and 90" in e for e in errors)


def test_invalid_photo_key_directory():
    data = {
        "category": "flood",
        "description": "Water overflowing storm drain.",
        "approximateLocation": "River Rd",
        "photoKey": "secret_bucket/malicious.exe",  # Not in uploads/
    }
    errors = validate_incident_submission(data)
    assert any("uploads/" in e for e in errors)


def test_invalid_risk_factor():
    data = {
        "category": "flood",
        "description": "Water overflowing storm drain.",
        "approximateLocation": "River Rd",
        "riskFactors": ["not_a_valid_factor"],
    }
    errors = validate_incident_submission(data)
    assert any("Unknown risk factors" in e for e in errors)


def test_valid_upload():
    data = {"contentType": "image/jpeg", "filename": "damage.jpg"}
    assert validate_upload(data) == []


def test_invalid_upload_content_type():
    data = {"contentType": "application/x-sh", "filename": "script.sh"}
    errors = validate_upload(data)
    assert any("contentType" in e for e in errors)


def test_valid_update():
    data = {"description": "Updated situation report: fire crews on scene."}
    assert validate_update(data) == []


def test_update_status_forbidden_for_public():
    data = {"status": "Resolved"}
    errors = validate_update(data)
    assert any("not permitted to modify incident status" in e for e in errors)


def test_update_unknown_field():
    data = {"unauthorizedField": "value"}
    errors = validate_update(data)
    assert any("Unknown fields" in e for e in errors)
