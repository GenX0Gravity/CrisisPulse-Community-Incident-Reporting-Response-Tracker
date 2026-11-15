"""Serverless Static Web Asset Handler for API Gateway HTTP API.

Serves the CrisisPulse HTML, CSS, and JS frontend assets over HTTPS.
"""

import base64
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

MIME_MAP = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".svg": "image/svg+xml",
    ".ico": "image/x-icon",
}


def handler(event, context):
    raw_path = (event.get("rawPath") or "").strip()
    
    # If accessed without trailing slash on stage (e.g. /prod), redirect to /prod/
    if raw_path == "/prod":
        return {
            "statusCode": 302,
            "headers": {"Location": "/prod/"},
            "body": "",
        }

    # Proxy path parameter from API Gateway HTTP API
    proxy_path = (event.get("pathParameters") or {}).get("proxy", "")

    # Strip stage prefix e.g. /prod/ from raw_path if proxy is not present
    if not proxy_path:
        clean_path = raw_path
        if clean_path.startswith("/prod/"):
            clean_path = clean_path[5:]
        elif clean_path == "/prod":
            clean_path = "/"
        req_file = clean_path.lstrip("/")
    else:
        req_file = proxy_path.lstrip("/")

    # Resolve file path
    if not req_file or req_file in ["", "index.html"]:
        file_path = os.path.join(BASE_DIR, "index.html")
    else:
        norm_path = os.path.normpath(req_file)
        if norm_path.startswith("..") or os.path.isabs(norm_path):
            return {"statusCode": 403, "body": "Forbidden"}
        file_path = os.path.join(BASE_DIR, norm_path)

    # If file doesn't exist: 404 for asset extensions, fallback to index.html for page routes
    if not os.path.isfile(file_path):
        ext = os.path.splitext(file_path)[1].lower()
        if ext in MIME_MAP and ext != ".html":
            return {"statusCode": 404, "body": "Asset not found"}
        file_path = os.path.join(BASE_DIR, "index.html")

    ext = os.path.splitext(file_path)[1].lower()
    content_type = MIME_MAP.get(ext, "application/octet-stream")

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            body = f.read()
        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": content_type,
                "Cache-Control": "public, max-age=0, must-revalidate" if ext == ".html" else "public, max-age=86400",
            },
            "body": body,
        }
    except UnicodeDecodeError:
        with open(file_path, "rb") as f:
            raw_bytes = f.read()
        return {
            "statusCode": 200,
            "headers": {
                "Content-Type": content_type,
                "Cache-Control": "public, max-age=86400",
            },
            "isBase64Encoded": True,
            "body": base64.b64encode(raw_bytes).decode("ascii"),
        }
    except Exception as exc:
        return {"statusCode": 500, "body": f"Error loading asset: {exc}"}
