"""Convenient one-command test runner for CrisisPulse.

Usage:
    python run_tests.py
"""

import os
import sys

# Ensure src is importable
root_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(root_dir, "src"))

# Set test environment variables
os.environ.setdefault("TABLE_NAME", "test-incidents")
os.environ.setdefault("PHOTO_BUCKET", "test-photos")
os.environ.setdefault("DEMO_MODE", "true")
os.environ.setdefault("FRONTEND_ORIGIN", "http://localhost:3000")

import tests.unit.test_health as th
import tests.unit.test_scoring as ts
import tests.unit.test_duplicate_detection as td
import tests.unit.test_validators as tv
import tests.unit.test_idempotency as ti
import tests.unit.test_workflow as tw
import tests.unit.test_lifecycle as tl
import tests.unit.test_coordinator_auth as tc

def main():
    suites = [
        ("Health Endpoint", th),
        ("Deterministic Priority Scoring", ts),
        ("Bounded Duplicate Detection", td),
        ("Input Validators", tv),
        ("Submission Idempotency", ti),
        ("Step Functions Workflow Task", tw),
        ("Lifecycle State Transitions", tl),
        ("Coordinator Authorization & Security", tc),
    ]

    total_passed = 0
    total_failed = 0

    print("=" * 65)
    print(" CrisisPulse Automated Test Suite")
    print("=" * 65)

    for suite_name, module in suites:
        test_funcs = [getattr(module, f) for f in dir(module) if f.startswith("test_")]
        passed_in_suite = 0
        failed_in_suite = 0

        for func in test_funcs:
            try:
                func()
                passed_in_suite += 1
            except Exception as exc:
                failed_in_suite += 1
                print(f"  [FAIL] {func.__name__}: {exc}")

        total_passed += passed_in_suite
        total_failed += failed_in_suite
        status_icon = "✓" if failed_in_suite == 0 else "✗"
        print(f" {status_icon} {suite_name:<38} ({passed_in_suite}/{len(test_funcs)} passed)")

    print("=" * 65)
    if total_failed == 0:
        print(f" SUCCESS: All {total_passed} tests passed cleanly!")
    else:
        print(f" FAILURE: {total_failed} test(s) failed out of {total_passed + total_failed}.")
    print("=" * 65)

    sys.exit(0 if total_failed == 0 else 1)

if __name__ == "__main__":
    main()
