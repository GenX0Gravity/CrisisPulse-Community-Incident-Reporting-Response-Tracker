"""Unit tests for deterministic priority scoring."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

from shared.scoring import (
    calculate_priority_score,
    PRIORITY_CRITICAL_THRESHOLD,
    PRIORITY_HIGH_THRESHOLD,
    PRIORITY_MEDIUM_THRESHOLD,
)


def test_fire_with_critical_risk_factors():
    result = calculate_priority_score(
        category="fire",
        risk_factors=["life_threat", "active_fire"],
    )
    # Fire base: 45 + life_threat: 40 + active_fire: 35 = 120 -> clamped to 100
    assert result["priority"] == "Critical"
    assert result["score"] == 100
    assert "Critical" in result["explanation"]
    assert "deterministic rule-based" in result["explanation"]
    assert "no AI model inference" in result["explanation"]
    assert result["evaluationType"] == "deterministic_rule_based"


def test_medical_with_injuries():
    result = calculate_priority_score(
        category="medical",
        risk_factors=["injuries_reported"],
    )
    # Medical base: 40 + injuries: 40 = 80 -> Critical
    assert result["priority"] == "Critical"
    assert result["score"] == 80


def test_flood_without_risk_factors():
    result = calculate_priority_score(category="flood")
    # Flood base: 35 -> Medium (25-49)
    assert result["priority"] == "Medium"
    assert result["score"] == 35
    assert "No additional risk factors were reported" in result["explanation"]


def test_weather_with_road_blocked_and_power_lines():
    result = calculate_priority_score(
        category="weather",
        risk_factors=["major_road_blocked", "downed_power_lines"],
    )
    # Weather base: 25 + road: 20 + lines: 25 = 70 -> High (50-74)
    assert result["priority"] == "High"
    assert result["score"] == 70


def test_other_minimal():
    result = calculate_priority_score(category="other")
    # Other base: 10 -> Low (< 25)
    assert result["priority"] == "Low"
    assert result["score"] == 10


def test_unknown_category_fallback():
    result = calculate_priority_score(category="unrecognized_category_xyz")
    assert result["score"] == 10
    assert result["priority"] == "Low"


def test_duplicate_risk_factors_deduplication():
    # Providing the same risk factor multiple times must not inflate points
    result = calculate_priority_score(
        category="accident",
        risk_factors=["injuries_reported", "injuries_reported"],
    )
    # Accident base: 25 + injuries: 40 = 65 -> High
    assert result["score"] == 65
    assert result["priority"] == "High"
