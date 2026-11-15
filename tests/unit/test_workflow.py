"""Unit tests for the Step Functions processing task."""

import os
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

os.environ.setdefault("TABLE_NAME", "test-incidents")
os.environ.setdefault("PHOTO_BUCKET", "test-photos")
os.environ.setdefault("DEMO_MODE", "true")
os.environ.setdefault("FRONTEND_ORIGIN", "http://localhost:3000")

from handlers.process_incident import handler as process_handler


@patch("handlers.process_incident.find_duplicate_incidents")
def test_process_incident_normal_triage(mock_find_duplicates):
    mock_find_duplicates.return_value = {
        "isPotentialDuplicate": False,
        "duplicateCount": 0,
        "candidates": [],
        "reason": "No duplicates detected within 300m.",
    }

    event = {
        "incidentId": "inc-test-101",
        "category": "fire",
        "description": "Flames spotted on 2nd floor balcony.",
        "approximateLocation": "Market St & 3rd",
        "latitude": 37.7891,
        "longitude": -122.4014,
        "photoKey": "uploads/flames.jpg",
        "riskFactors": ["active_fire"],
        "createdAt": "2026-11-15T10:00:00Z",
    }

    result = process_handler(event, None)

    assert result["incidentId"] == "inc-test-101"
    # Canonical status after Step Functions enrichment is 'Under Review'
    assert result["status"] == "Under Review"
    assert result["priority"] == "Critical"
    assert result["priorityScore"] == 80
    assert result["isPotentialDuplicate"] is False
    assert result["photoValidation"]["valid"] is True
    assert "historyEntry" in result
    assert result["historyEntry"]["status"] == "Under Review"
    assert "processedAt" in result


@patch("handlers.process_incident.find_duplicate_incidents")
def test_process_incident_flagged_duplicate(mock_find_duplicates):
    mock_find_duplicates.return_value = {
        "isPotentialDuplicate": True,
        "duplicateCount": 1,
        "candidates": [
            {
                "incidentId": "inc-prior-001",
                "distanceMeters": 45.2,
                "createdAt": "2026-11-15T09:30:00Z",
            }
        ],
        "reason": "Matching report 45.2m away.",
    }

    event = {
        "incidentId": "inc-test-102",
        "category": "accident",
        "description": "Fender bender blocking right lane.",
        "approximateLocation": "5th Ave",
        "latitude": 40.7128,
        "longitude": -74.0060,
        "photoKey": "",
        "riskFactors": [],
        "createdAt": "2026-11-15T10:00:00Z",
    }

    result = process_handler(event, None)

    assert result["incidentId"] == "inc-test-102"
    assert result["status"] == "Under Review"
    assert result["isPotentialDuplicate"] is True
    assert result["duplicateCount"] == 1
    assert "45.2m" in result["historyEntry"]["notes"]
