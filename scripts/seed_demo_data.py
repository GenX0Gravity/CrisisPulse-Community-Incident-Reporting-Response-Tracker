"""Developer-only synthetic seed script for CrisisPulse.

Generates clearly labeled synthetic incident records directly into DynamoDB.
Does NOT invoke production API endpoints or publish unverified reports.

Usage:
    python scripts/seed_demo_data.py [--table-name TABLE_NAME] [--region REGION] [--dry-run]
"""

import argparse
import json
import os
import sys
import time
import uuid
from decimal import Decimal

# Ensure src is on path for shared utilities
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from shared.lifecycle import create_history_entry
from shared.scoring import calculate_priority_score

try:
    import boto3
except ImportError:
    boto3 = None


def generate_synthetic_incidents() -> list[dict]:
    """Generate clearly labeled synthetic demonstration incidents."""
    now = time.time()
    t_0 = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now - 7200))
    t_1 = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now - 7190))
    t_2 = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now - 3600))
    t_3 = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now - 1800))
    t_4 = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now - 300))

    inc_1_id = "demo-synth-fire-001"
    inc_2_id = "demo-synth-fire-dup-002"
    inc_3_id = "demo-synth-med-003"
    inc_4_id = "demo-synth-hazmat-004"
    inc_5_id = "demo-synth-infra-005"

    inc_1_score = calculate_priority_score("fire", ["active_fire", "life_threat", "trapped_individuals"])
    inc_2_score = calculate_priority_score("fire", ["active_fire"])
    inc_3_score = calculate_priority_score("medical", ["injuries_reported"])
    inc_4_score = calculate_priority_score("hazmat", ["hazardous_materials", "vulnerable_population"])
    inc_5_score = calculate_priority_score("infrastructure", ["major_road_blocked"])

    incidents = [
        # 1. Critical Active Fire (In Progress)
        {
            "incidentId": inc_1_id,
            "entityType": "INCIDENT",
            "isSynthetic": True,
            "syntheticLabel": "DEMO-SYNTHETIC-DATA",
            "category": "fire",
            "title": "[SYNTHETIC DEMO] Multi-Alarm Commercial Structure Fire",
            "description": "Heavy black smoke and visible second-floor flames. Multiple units responding.",
            "approximateLocation": "4th Ave & Pine St (Demonstration District)",
            "latitude": Decimal("40.712800"),
            "longitude": Decimal("-74.006000"),
            "riskFactors": ["active_fire", "life_threat", "trapped_individuals"],
            "status": "In Progress",
            "priority": inc_1_score["priority"],
            "priorityScore": Decimal(str(inc_1_score["score"])),
            "priorityExplanation": inc_1_score["explanation"],
            "isPotentialDuplicate": False,
            "statusHistory": [
                create_history_entry("Reported", "demo_reporter", "Incident reported by synthetic observer.", t_0),
                create_history_entry("Under Review", "step-functions", "Automated priority triage completed.", t_1),
                create_history_entry("In Progress", "coordinator_lead", "Engine 4 and Ladder 2 dispatched to scene.", t_2),
            ],
            "reporterName": "Synthetic Demo Generator",
            "createdAt": t_0,
            "updatedAt": t_2,
        },
        # 2. Duplicate Report of Incident 1 (~85m away, 1 hour later)
        {
            "incidentId": inc_2_id,
            "entityType": "INCIDENT",
            "isSynthetic": True,
            "syntheticLabel": "DEMO-SYNTHETIC-DATA",
            "category": "fire",
            "title": "[SYNTHETIC DEMO] Smoke and Fire on 4th Ave",
            "description": "Thick smoke visible from intersection. Fire trucks already on site.",
            "approximateLocation": "4th Ave & Olive St (~85m from Fire 001)",
            "latitude": Decimal("40.713500"),  # ~78 meters north
            "longitude": Decimal("-74.006000"),
            "riskFactors": ["active_fire"],
            "status": "Under Review",
            "priority": inc_2_score["priority"],
            "priorityScore": Decimal(str(inc_2_score["score"])),
            "priorityExplanation": inc_2_score["explanation"],
            "isPotentialDuplicate": True,
            "duplicateCount": 1,
            "duplicateReason": f"Detected matching report in category 'fire' within 24 hours. Nearest incident '{inc_1_id}' is 77.8m away.",
            "duplicateCandidates": [
                {
                    "incidentId": inc_1_id,
                    "title": "[SYNTHETIC DEMO] Multi-Alarm Commercial Structure Fire",
                    "distanceMeters": 77.8,
                    "createdAt": t_0,
                    "status": "In Progress",
                }
            ],
            "statusHistory": [
                create_history_entry("Reported", "demo_reporter_2", "Duplicate report submitted by secondary observer.", t_2),
                create_history_entry("Under Review", "step-functions", f"Flagged as duplicate candidate of incident {inc_1_id} (77.8m away).", t_2),
            ],
            "reporterName": "Synthetic Demo Generator",
            "createdAt": t_2,
            "updatedAt": t_2,
        },
        # 3. Resolved Medical Incident
        {
            "incidentId": inc_3_id,
            "entityType": "INCIDENT",
            "isSynthetic": True,
            "syntheticLabel": "DEMO-SYNTHETIC-DATA",
            "category": "medical",
            "title": "[SYNTHETIC DEMO] Heat Exhaustion at Public Plaza",
            "description": "Elderly individual collapsed on bench. Conscious and receiving paramedic care.",
            "approximateLocation": "Civic Center Plaza",
            "latitude": Decimal("40.715000"),
            "longitude": Decimal("-74.002000"),
            "riskFactors": ["injuries_reported"],
            "status": "Resolved",
            "priority": inc_3_score["priority"],
            "priorityScore": Decimal(str(inc_3_score["score"])),
            "priorityExplanation": inc_3_score["explanation"],
            "isPotentialDuplicate": False,
            "statusHistory": [
                create_history_entry("Reported", "plaza_patrol", "Observer reported medical emergency.", t_0),
                create_history_entry("Under Review", "step-functions", "High priority automated triage.", t_1),
                create_history_entry("In Progress", "medic_dispatch", "Ambulance Unit 12 arrived.", t_2),
                create_history_entry("Resolved", "medic_dispatch", "Patient stabilized and transported. Scene clear.", t_3),
            ],
            "coordinatorNotes": "Transported to Memorial Hospital. Clear of plaza.",
            "reporterName": "Synthetic Demo Generator",
            "createdAt": t_0,
            "updatedAt": t_3,
        },
        # 4. Hazmat Chemical Spill (Under Review)
        {
            "incidentId": inc_4_id,
            "entityType": "INCIDENT",
            "isSynthetic": True,
            "syntheticLabel": "DEMO-SYNTHETIC-DATA",
            "category": "hazmat",
            "title": "[SYNTHETIC DEMO] Industrial Solvent Spill on Loading Dock",
            "description": "55-gallon drum punctured during forklift transport. Pungent vapor cloud expanding toward elementary school.",
            "approximateLocation": "Industrial Way & Dock St",
            "latitude": Decimal("40.720000"),
            "longitude": Decimal("-74.010000"),
            "riskFactors": ["hazardous_materials", "vulnerable_population"],
            "status": "Under Review",
            "priority": inc_4_score["priority"],
            "priorityScore": Decimal(str(inc_4_score["score"])),
            "priorityExplanation": inc_4_score["explanation"],
            "isPotentialDuplicate": False,
            "statusHistory": [
                create_history_entry("Reported", "warehouse_mgr", "Spill reported via public portal.", t_3),
                create_history_entry("Under Review", "step-functions", "Deterministic scoring triggered High priority.", t_4),
            ],
            "reporterName": "Synthetic Demo Generator",
            "createdAt": t_3,
            "updatedAt": t_4,
        },
        # 5. Freshly Reported Infrastructure Hazard
        {
            "incidentId": inc_5_id,
            "entityType": "INCIDENT",
            "isSynthetic": True,
            "syntheticLabel": "DEMO-SYNTHETIC-DATA",
            "category": "infrastructure",
            "title": "[SYNTHETIC DEMO] Deep Pothole & Water Main Leak",
            "description": "Water bubbling up through road surface causing localized traffic backup.",
            "approximateLocation": "Oak Ave & 12th St",
            "latitude": Decimal("40.708000"),
            "longitude": Decimal("-74.015000"),
            "riskFactors": ["major_road_blocked"],
            "status": "Reported",
            "priority": inc_5_score["priority"],
            "priorityScore": Decimal(str(inc_5_score["score"])),
            "priorityExplanation": inc_5_score["explanation"],
            "isPotentialDuplicate": False,
            "statusHistory": [
                create_history_entry("Reported", "commuter_bob", "Reported by commuter.", t_4),
            ],
            "reporterName": "Synthetic Demo Generator",
            "createdAt": t_4,
            "updatedAt": t_4,
        },
    ]

    return incidents


def main():
    parser = argparse.ArgumentParser(description="Seed synthetic demo incidents into CrisisPulse DynamoDB")
    parser.add_argument("--table-name", default=os.environ.get("TABLE_NAME", "CrisisPulse-incidents"), help="DynamoDB Table Name")
    parser.add_argument("--region", default=os.environ.get("AWS_DEFAULT_REGION", "us-east-1"), help="AWS Region")
    parser.add_argument("--dry-run", action="store_true", help="Print synthetic records without writing to DynamoDB")
    args = parser.parse_args()

    incidents = generate_synthetic_incidents()

    print(f"\n=======================================================")
    print(f"CrisisPulse Synthetic Demo Data Generator")
    print(f"Target DynamoDB Table: {args.table_name} ({args.region})")
    print(f"Total Synthetic Incidents: {len(incidents)}")
    print(f"=======================================================\n")

    if args.dry_run:
        print("[DRY-RUN] Records prepared (not written to AWS):")
        for inc in incidents:
            print(f" - [{inc['priority']}] [{inc['status']}] {inc['incidentId']}: {inc['title']}")
            print(f"   Score: {inc['priorityScore']}/100 | History entries: {len(inc['statusHistory'])}")
            if inc.get("isPotentialDuplicate"):
                print(f"   Duplicate Candidate: {inc['duplicateReason']}")
        print("\nDry-run completed successfully.")
        return

    if not boto3:
        print("ERROR: boto3 is required to write to DynamoDB. Install with `pip install boto3` or use --dry-run.")
        sys.exit(1)

    try:
        dynamodb = boto3.resource("dynamodb", region_name=args.region)
        table = dynamodb.Table(args.table_name)

        for inc in incidents:
            print(f"Seeding {inc['incidentId']} ({inc['status']})...", end=" ")
            table.put_item(Item=inc)
            print("OK")

        print("\nAll synthetic demonstration records successfully seeded!")
    except Exception as exc:
        print(f"\nERROR writing to DynamoDB: {exc}")
        print("Ensure your AWS credentials are valid and you have dynamodb:PutItem permission.")
        sys.exit(1)


if __name__ == "__main__":
    main()
