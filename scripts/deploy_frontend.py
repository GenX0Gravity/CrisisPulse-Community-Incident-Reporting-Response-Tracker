"""CrisisPulse Static Frontend S3 Deployer.

Uploads frontend assets to the deployed CloudFront origin S3 bucket with
appropriate Content-Type and Cache-Control headers. Works standalone using
Python and boto3 (or prompts if boto3 is missing).

Usage:
    python scripts/deploy_frontend.py <FrontendBucketName> [--region <region>]
"""

import mimetypes
import os
import sys

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.join(ROOT_DIR, "frontend")


def get_content_type(file_path: str) -> str:
    """Determine MIME content type with fallback defaults."""
    ctype, _ = mimetypes.guess_type(file_path)
    if ctype:
        return ctype
    ext = os.path.splitext(file_path)[1].lower()
    return {
        ".html": "text/html",
        ".css": "text/css",
        ".js": "application/javascript",
        ".json": "application/json",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".svg": "image/svg+xml",
        ".ico": "image/x-icon",
    }.get(ext, "application/octet-stream")


def get_cache_control(file_path: str) -> str:
    """Return cache headers: no-cache for HTML, longer caching for static assets."""
    if file_path.endswith(".html"):
        return "public, max-age=0, must-revalidate"
    return "public, max-age=86400"


def deploy_frontend(bucket_name: str, region: str = "us-east-1"):
    try:
        import boto3
    except ImportError:
        print("[!] ERROR: boto3 is required to upload frontend to S3.")
        print("    Install it via: pip install boto3")
        sys.exit(1)

    s3_client = boto3.client("s3", region_name=region)
    print(f"[*] Deploying frontend assets from: {FRONTEND_DIR}")
    print(f"[*] Target S3 Bucket: {bucket_name} (Region: {region})")
    print("-" * 60)

    uploaded_count = 0
    for root, _, files in os.walk(FRONTEND_DIR):
        for fname in files:
            full_path = os.path.join(root, fname)
            rel_path = os.path.relpath(full_path, FRONTEND_DIR).replace("\\", "/")
            ctype = get_content_type(full_path)
            cache_ctrl = get_cache_control(full_path)

            print(f" -> Uploading: {rel_path} ({ctype})")
            with open(full_path, "rb") as f:
                s3_client.put_object(
                    Bucket=bucket_name,
                    Key=rel_path,
                    Body=f.read(),
                    ContentType=ctype,
                    CacheControl=cache_ctrl,
                )
            uploaded_count += 1

    print("-" * 60)
    print(f"[✓] Successfully deployed {uploaded_count} frontend assets to s3://{bucket_name}/")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/deploy_frontend.py <FrontendBucketName> [--region <region>]")
        sys.exit(1)

    target_bucket = sys.argv[1]
    target_region = "us-east-1"
    if "--region" in sys.argv:
        idx = sys.argv.index("--region")
        if idx + 1 < len(sys.argv):
            target_region = sys.argv[idx + 1]

    deploy_frontend(target_bucket, target_region)
