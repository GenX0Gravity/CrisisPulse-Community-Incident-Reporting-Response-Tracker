"""Deterministic priority scoring engine for CrisisPulse incidents.

NOTE: This system uses transparent, deterministic rule-based scoring derived
strictly from the incident category and explicitly reported risk factors.
It does NOT use AI or machine learning model inference.
"""

from __future__ import annotations

from typing import Any

# Base score weights by incident category (0 to 45)
CATEGORY_BASE_SCORES: dict[str, int] = {
    "fire": 45,
    "hazmat": 45,
    "medical": 40,
    "flood": 35,
    "infrastructure": 30,
    "accident": 25,
    "weather": 25,
    "crime": 25,
    "environmental": 20,
    "other": 10,
}

# Explicit risk factors and their additive point values (0 to 40)
# Risk factors represent concrete, observable conditions reported by observers.
RISK_FACTOR_WEIGHTS: dict[str, dict[str, Any]] = {
    "injuries_reported": {
        "points": 40,
        "label": "Casualties or injuries reported",
    },
    "life_threat": {
        "points": 40,
        "label": "Immediate threat to human life",
    },
    "active_fire": {
        "points": 35,
        "label": "Active, uncontained flames or fire spread",
    },
    "trapped_individuals": {
        "points": 35,
        "label": "Individuals trapped or unable to self-evacuate",
    },
    "hazardous_materials": {
        "points": 30,
        "label": "Chemical, biological, or radiological hazard present",
    },
    "vulnerable_population": {
        "points": 25,
        "label": "Direct proximity to school, hospital, or senior care facility",
    },
    "downed_power_lines": {
        "points": 25,
        "label": "Exposed high-voltage electrical wires or grid damage",
    },
    "major_road_blocked": {
        "points": 20,
        "label": "Primary transit or emergency evacuation corridor blocked",
    },
    "structural_instability": {
        "points": 20,
        "label": "Compromised foundation, walls, or risk of building collapse",
    },
    "water_contamination": {
        "points": 20,
        "label": "Drinking water supply or waterway compromised",
    },
}

# Priority level thresholds (Score 0-100)
# Critical: 75+
# High:     50-74
# Medium:   25-49
# Low:      0-24
PRIORITY_CRITICAL_THRESHOLD = 75
PRIORITY_HIGH_THRESHOLD = 50
PRIORITY_MEDIUM_THRESHOLD = 25


def calculate_priority_score(
    category: str,
    risk_factors: list[str] | None = None,
) -> dict[str, Any]:
    """Calculate deterministic priority score and produce a human-readable explanation.

    Args:
        category: Incident category string (e.g. 'fire', 'medical').
        risk_factors: List of string risk factors reported with the incident.

    Returns:
        dict containing:
            - priority: 'Low' | 'Medium' | 'High' | 'Critical'
            - score: integer (0-100 clamped)
            - explanation: Human-readable narrative detailing the deterministic score
            - breakdown: Dict detailing base score, triggered factors, and point additions
            - evaluationType: 'deterministic_rule_based'
    """
    cat_normalized = (category or "other").strip().lower()
    base_points = CATEGORY_BASE_SCORES.get(cat_normalized, 10)

    applied_factors: list[dict[str, Any]] = []
    risk_points = 0

    if risk_factors:
        # Normalize and deduplicate factors
        seen_factors = set()
        for rf in risk_factors:
            rf_clean = rf.strip().lower()
            if rf_clean in RISK_FACTOR_WEIGHTS and rf_clean not in seen_factors:
                seen_factors.add(rf_clean)
                factor_info = RISK_FACTOR_WEIGHTS[rf_clean]
                applied_factors.append({
                    "factor": rf_clean,
                    "label": factor_info["label"],
                    "points": factor_info["points"],
                })
                risk_points += factor_info["points"]

    total_score = min(100, base_points + risk_points)

    if total_score >= PRIORITY_CRITICAL_THRESHOLD:
        priority = "Critical"
    elif total_score >= PRIORITY_HIGH_THRESHOLD:
        priority = "High"
    elif total_score >= PRIORITY_MEDIUM_THRESHOLD:
        priority = "Medium"
    else:
        priority = "Low"

    # Construct transparent human-readable explanation
    explanation_parts = [
        f"Assigned {priority} priority (score: {total_score}/100) via deterministic rule-based evaluation.",
        f"Base category '{cat_normalized}' contributed {base_points} points.",
    ]

    if applied_factors:
        factor_desc = ", ".join(
            f"{f['label']} (+{f['points']})" for f in applied_factors
        )
        explanation_parts.append(
            f"Evaluated {len(applied_factors)} reported risk factor(s): {factor_desc} adding {risk_points} points."
        )
    else:
        explanation_parts.append("No additional risk factors were reported.")

    explanation_parts.append(
        "Scoring is strictly rule-based with no AI model inference."
    )
    explanation = " ".join(explanation_parts)

    return {
        "priority": priority,
        "score": total_score,
        "explanation": explanation,
        "breakdown": {
            "category": cat_normalized,
            "categoryBasePoints": base_points,
            "appliedRiskFactors": applied_factors,
            "riskFactorPoints": risk_points,
            "totalScore": total_score,
        },
        "evaluationType": "deterministic_rule_based",
    }
