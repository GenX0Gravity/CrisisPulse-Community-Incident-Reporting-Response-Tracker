"""Unit tests for the health endpoint handler."""

import json
import os
import sys

# Ensure the src directory is on the path so shared/ is importable.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

# Set required env vars before importing handlers.
os.environ.setdefault("TABLE_NAME", "test-incidents")
os.environ.setdefault("PHOTO_BUCKET", "test-photos")
os.environ.setdefault("DEMO_MODE", "true")
os.environ.setdefault("FRONTEND_ORIGIN", "http://localhost:3000")


def test_health_returns_200():
    from handlers.health import handler

    result = handler({}, None)
    assert result["statusCode"] == 200

    body = json.loads(result["body"])
    assert body["status"] == "healthy"
    assert body["service"] == "CrisisPulse"
    assert body["version"] == "1.0.0"
    assert body["demoMode"] is True


def test_health_cors_header():
    from handlers.health import handler

    result = handler({}, None)
    assert result["headers"]["Access-Control-Allow-Origin"] == "http://localhost:3000"
