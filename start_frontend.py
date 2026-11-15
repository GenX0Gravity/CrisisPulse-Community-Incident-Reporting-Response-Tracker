"""CrisisPulse Integrated Local Development Server.

Serves the frontend UI on port 3000 while simultaneously running the
CrisisPulse API endpoints (/health, /incidents, /uploads, /coordinator)
with in-memory storage, deterministic scoring, duplicate detection,
and full lifecycle transitions.

Usage:
    python start_frontend.py [PORT]
"""

import http.server
import json
import os
import socketserver
import sys
import time
import urllib.parse
import uuid
import webbrowser
from decimal import Decimal

# Ensure src is on python path
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT_DIR, "src"))

from shared.lifecycle import (
    CANONICAL_STATUSES,
    create_history_entry,
    is_valid_transition,
    normalize_status,
)
from shared.scoring import calculate_priority_score
from shared.validators import (
    validate_incident_submission,
    validate_update,
    validate_upload,
)
from scripts.seed_demo_data import generate_synthetic_incidents

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 3000
FRONTEND_DIR = os.path.join(ROOT_DIR, "frontend")

# In-memory incident store pre-seeded with synthetic demonstration data
_LOCAL_INCIDENTS_STORE: dict[str, dict] = {}
_LOCAL_IDEMPOTENCY_STORE: dict[str, str] = {}


def _init_local_store():
    """Seed in-memory store with synthetic demo incidents."""
    seed_records = generate_synthetic_incidents()
    for inc in seed_records:
        # Convert Decimal values to float/int for JSON serialization
        clean_inc = {}
        for k, v in inc.items():
            if isinstance(v, Decimal):
                clean_inc[k] = float(v)
            else:
                clean_inc[k] = v
        _LOCAL_INCIDENTS_STORE[clean_inc["incidentId"]] = clean_inc


_init_local_store()


class IntegratedDevServerHandler(http.server.SimpleHTTPRequestHandler):
    """Handles both static frontend assets and local API Gateway emulation."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=FRONTEND_DIR, **kwargs)

    def _send_cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PATCH, OPTIONS")
        self.send_header(
            "Access-Control-Allow-Headers",
            "Content-Type, Authorization, Idempotency-Key, X-Idempotency-Key",
        )

    def do_OPTIONS(self):
        """Handle CORS pre-flight requests."""
        self.send_response(204)
        self._send_cors_headers()
        self.end_headers()

    def _send_json(self, data: dict, status_code: int = 200):
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self._send_cors_headers()
        self.end_headers()
        self.wfile.write(json.dumps(data, default=str).encode("utf-8"))

    def _read_body_json(self) -> dict:
        content_len = int(self.headers.get("Content-Length", 0))
        if content_len == 0:
            return {}
        raw = self.rfile.read(content_len)
        try:
            return json.loads(raw.decode("utf-8"))
        except Exception:
            return {}

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        # 1. API: GET /health
        if path == "/health":
            return self._send_json({
                "status": "healthy",
                "service": "CrisisPulse",
                "version": "1.0.0",
                "mode": "local_dev_server",
                "demoMode": True,
                "timestamp": int(time.time()),
            })

        # 2. API: GET /incidents
        if path == "/incidents":
            incidents_list = list(_LOCAL_INCIDENTS_STORE.values())
            # Sort newest first by createdAt
            incidents_list.sort(key=lambda x: x.get("createdAt", ""), reverse=True)
            return self._send_json({
                "incidents": incidents_list,
                "count": len(incidents_list),
            })

        # 3. API: GET /incidents/{id}
        if path.startswith("/incidents/"):
            incident_id = path.replace("/incidents/", "").strip()
            item = _LOCAL_INCIDENTS_STORE.get(incident_id)
            if not item:
                return self._send_json({"error": "Incident not found"}, 404)

            # Attach local photo URL if photoKey exists
            item_copy = dict(item)
            if item_copy.get("photoKey"):
                item_copy["photoUrl"] = (
                    f"https://via.placeholder.com/600x400/0f172a/22d3ee?text=Incident+Photo+{incident_id[:8]}"
                )
            return self._send_json({"incident": item_copy})

        # Fallback: Serve static frontend files
        return super().do_GET()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        # 1. API: POST /uploads
        if path == "/uploads":
            body = self._read_body_json()
            errors = validate_upload(body)
            if errors:
                return self._send_json({"error": "; ".join(errors)}, 400)

            key = f"uploads/{uuid.uuid4()}.jpg"
            return self._send_json({
                "uploadUrl": f"http://localhost:{PORT}/uploads/mock-presigned",
                "photoKey": key,
                "expiresIn": 300,
                "maxSizeBytes": 5242880,
                "contentType": body.get("contentType", "image/jpeg"),
            }, 201)

        # 2. API: POST /incidents
        if path == "/incidents":
            body = self._read_body_json()
            errors = validate_incident_submission(body)
            if errors:
                return self._send_json({"error": "; ".join(errors)}, 400)

            # Check idempotency
            idemp_key = (
                self.headers.get("Idempotency-Key")
                or self.headers.get("X-Idempotency-Key")
                or body.get("idempotencyKey")
            )
            if idemp_key and idemp_key in _LOCAL_IDEMPOTENCY_STORE:
                existing_id = _LOCAL_IDEMPOTENCY_STORE[idemp_key]
                existing_inc = _LOCAL_INCIDENTS_STORE.get(existing_id)
                if existing_inc:
                    return self._send_json({
                        "incident": existing_inc,
                        "idempotentReplay": True,
                        "message": "Returned existing incident matching idempotency key.",
                    }, 200)

            incident_id = str(uuid.uuid4())
            now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

            category = body["category"].strip().lower()
            risk_factors = body.get("riskFactors") or []
            scoring = calculate_priority_score(category, risk_factors)

            # Check local duplicate detection (within 300m, 24h)
            lat = body.get("latitude")
            lon = body.get("longitude")
            is_dup = False
            dup_reason = ""
            dup_candidates = []

            if lat is not None and lon is not None:
                for existing in _LOCAL_INCIDENTS_STORE.values():
                    if existing.get("category") == category and existing.get("latitude"):
                        # Rough distance check
                        d_lat = abs(float(existing["latitude"]) - float(lat))
                        d_lon = abs(float(existing["longitude"]) - float(lon))
                        if d_lat < 0.003 and d_lon < 0.003:  # roughly within ~300m
                            is_dup = True
                            dist_m = round((d_lat**2 + d_lon**2)**0.5 * 111000, 1)
                            dup_candidates.append({
                                "incidentId": existing["incidentId"],
                                "title": existing.get("title", ""),
                                "distanceMeters": dist_m,
                                "createdAt": existing.get("createdAt", ""),
                            })
                            dup_reason = f"Detected matching report in category '{category}' within 300m ({dist_m}m away)."
                            break

            # In local dev server, simulate Step Functions automated triage completing immediately to 'Under Review'
            initial_history = [
                create_history_entry("Reported", body.get("reporterName", "public_user"), "Initial submission received.", now_iso),
                create_history_entry("Under Review", "step-functions", f"Automated triage: {scoring['priority']} Priority ({scoring['score']}/100). {dup_reason or 'No duplicates.'}", now_iso),
            ]

            item = {
                "incidentId": incident_id,
                "category": category,
                "description": body["description"],
                "approximateLocation": body.get("approximateLocation") or body.get("approximate_location"),
                "reporterName": body.get("reporterName", "Anonymous"),
                "photoKey": body.get("photoKey", ""),
                "riskFactors": risk_factors,
                "status": "Under Review",
                "statusHistory": initial_history,
                "priority": scoring["priority"],
                "priorityScore": scoring["score"],
                "priorityExplanation": scoring["explanation"],
                "isPotentialDuplicate": is_dup,
                "duplicateReason": dup_reason,
                "duplicateCandidates": dup_candidates,
                "createdAt": now_iso,
                "updatedAt": now_iso,
                "workflowMetadata": {"state": "COMPLETED", "completedAt": now_iso},
            }

            if lat is not None and lon is not None:
                item["latitude"] = float(lat)
                item["longitude"] = float(lon)

            _LOCAL_INCIDENTS_STORE[incident_id] = item
            if idemp_key:
                _LOCAL_IDEMPOTENCY_STORE[idemp_key] = incident_id

            return self._send_json({
                "incidentId": incident_id,
                "status": item["status"],
                "priority": item["priority"],
                "createdAt": item["createdAt"],
                "incident": item,
            }, 201)

        # 3. API: POST /coordinator/incidents/{id}/status
        if "/coordinator/incidents/" in path and path.endswith("/status"):
            parts = path.split("/")
            incident_id = parts[3]
            body = self._read_body_json()

            # Check coordinator auth
            auth = self.headers.get("Authorization", "")
            if not auth or "bearer" not in auth.lower():
                return self._send_json({
                    "error": "Coordinator authorization required. Public users cannot modify incident status. Provide Bearer token or execute transitions via authenticated AWS Console operations."
                }, 401)

            target_status = normalize_status(body.get("status"))
            if not target_status:
                return self._send_json({
                    "error": f"Invalid status. Allowed: {', '.join(sorted(CANONICAL_STATUSES))}"
                }, 400)

            item = _LOCAL_INCIDENTS_STORE.get(incident_id)
            if not item:
                return self._send_json({"error": "Incident not found"}, 404)

            current_status = normalize_status(item.get("status", "Reported")) or "Reported"
            if not is_valid_transition(current_status, target_status):
                return self._send_json({
                    "error": f"Illegal status transition: cannot transition from '{current_status}' to '{target_status}'."
                }, 400)

            now_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            notes = body.get("notes") or f"Transitioned from {current_status} to {target_status} by coordinator."
            new_entry = create_history_entry(target_status, "local_coordinator", notes, now_iso)

            item["status"] = target_status
            item["statusHistory"] = (item.get("statusHistory") or []) + [new_entry]
            item["updatedAt"] = now_iso

            return self._send_json({
                "incident": item,
                "transition": {
                    "previousStatus": current_status,
                    "currentStatus": target_status,
                    "actor": "local_coordinator",
                    "timestamp": now_iso,
                },
            }, 200)

        self.send_error(404, "Endpoint not found")

    def do_PATCH(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path.startswith("/incidents/"):
            incident_id = path.replace("/incidents/", "").strip()
            body = self._read_body_json()

            # Forbid public status updates
            if "status" in body:
                return self._send_json({
                    "error": "Public users are not permitted to modify incident status. Status updates require coordinator authorization via /coordinator/incidents/{id}/status."
                }, 403)

            errors = validate_update(body)
            if errors:
                return self._send_json({"error": "; ".join(errors)}, 400)

            item = _LOCAL_INCIDENTS_STORE.get(incident_id)
            if not item:
                return self._send_json({"error": "Incident not found"}, 404)

            for k, v in body.items():
                item[k] = v
            item["updatedAt"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

            return self._send_json({"incident": item}, 200)

        self.send_error(404, "Endpoint not found")


class ReusableTCPServer(socketserver.TCPServer):
    allow_reuse_address = True


def main():
    candidate_ports = [PORT] if len(sys.argv) > 1 else [8000, 8080, 3000, 3001]
    httpd = None
    selected_port = None

    for port in candidate_ports:
        try:
            httpd = ReusableTCPServer(("127.0.0.1", port), IntegratedDevServerHandler)
            selected_port = port
            break
        except OSError as err:
            # Port busy or blocked by Windows OS reserved ranges
            print(f"[*] Port {port} unavailable ({err.strerror or err}), trying next port...")
            continue

    if not httpd:
        print("[!] ERROR: Unable to bind to any candidate port (tried: {candidate_ports}).")
        sys.exit(1)

    with httpd:
        url = f"http://localhost:{selected_port}"
        print("=" * 65)
        print(" 🚨 CrisisPulse Integrated Local Development Server")
        print(f" Serving Frontend UI + API Endpoints on: {url}")
        print(f" Pre-seeded with 5 Synthetic Demonstration Incidents")
        print(" Press Ctrl+C to stop.")
        print("=" * 65)

        try:
            webbrowser.open(url)
        except Exception:
            pass

        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nServer stopped.")


if __name__ == "__main__":
    main()
