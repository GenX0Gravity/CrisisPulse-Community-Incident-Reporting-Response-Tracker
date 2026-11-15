"""Unit tests for Haversine distance and bounded duplicate detection."""

import os
import sys
from unittest.mock import MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

from shared.duplicate_detection import (
    calculate_haversine_distance,
    find_duplicate_incidents,
)


def test_haversine_identical_points():
    dist = calculate_haversine_distance(40.7128, -74.0060, 40.7128, -74.0060)
    assert round(dist, 2) == 0.0


def test_haversine_close_points():
    # Roughly 110 meters apart in latitude (0.001 deg lat is ~111m)
    lat1, lon1 = 40.71280, -74.0060
    lat2, lon2 = 40.71380, -74.0060
    dist = calculate_haversine_distance(lat1, lon1, lat2, lon2)
    assert 100 < dist < 120


def test_haversine_far_points():
    # Roughly 1100 meters apart (0.01 deg lat)
    lat1, lon1 = 40.71280, -74.0060
    lat2, lon2 = 40.72280, -74.0060
    dist = calculate_haversine_distance(lat1, lon1, lat2, lon2)
    assert 1000 < dist < 1200


def test_duplicate_detection_finds_close_report():
    mock_table = MagicMock()
    # Mock DynamoDB GSI bounded query returning 1 nearby incident (110m away)
    mock_table.query.return_value = {
        "Items": [
            {
                "incidentId": "existing-incident-001",
                "title": "Smoke at 5th and Main",
                "category": "fire",
                "latitude": 40.71380,
                "longitude": -74.0060,
                "createdAt": "2026-11-15T10:00:00Z",
                "status": "triaged",
            }
        ]
    }

    result = find_duplicate_incidents(
        table=mock_table,
        incident_id="new-incident-999",
        category="fire",
        latitude=40.71280,
        longitude=-74.0060,
        current_time_iso="2026-11-15T11:00:00Z",
    )

    assert result["isPotentialDuplicate"] is True
    assert result["duplicateCount"] == 1
    assert result["candidates"][0]["incidentId"] == "existing-incident-001"
    assert result["candidates"][0]["distanceMeters"] < 300.0
    # Verifies GSI query was called
    mock_table.query.assert_called_once()
    assert mock_table.query.call_args[1]["IndexName"] == "category-createdAt-index"


def test_duplicate_detection_ignores_distant_report():
    mock_table = MagicMock()
    # Mock DynamoDB GSI returning an incident ~1100m away (exceeding 300m threshold)
    mock_table.query.return_value = {
        "Items": [
            {
                "incidentId": "distant-incident-002",
                "title": "Distant fire",
                "category": "fire",
                "latitude": 40.72280,
                "longitude": -74.0060,
                "createdAt": "2026-11-15T10:00:00Z",
                "status": "triaged",
            }
        ]
    }

    result = find_duplicate_incidents(
        table=mock_table,
        incident_id="new-incident-999",
        category="fire",
        latitude=40.71280,
        longitude=-74.0060,
        current_time_iso="2026-11-15T11:00:00Z",
    )

    assert result["isPotentialDuplicate"] is False
    assert result["duplicateCount"] == 0
    assert len(result["candidates"]) == 0


def test_duplicate_detection_skips_when_no_coordinates():
    mock_table = MagicMock()
    result = find_duplicate_incidents(
        table=mock_table,
        incident_id="new-incident-999",
        category="fire",
        latitude=None,
        longitude=None,
    )
    assert result["isPotentialDuplicate"] is False
    mock_table.query.assert_not_called()
