"""GET /health — liveness check."""

import time

from shared.config import DEMO_MODE
from shared.response import success


def handler(event, context):
    return success({
        "status": "healthy",
        "service": "CrisisPulse",
        "timestamp": int(time.time()),
        "version": "1.0.0",
        "demoMode": DEMO_MODE,
    })
