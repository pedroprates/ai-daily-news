#!/usr/bin/env python3
"""Uploads the build/ directory to S3 and optionally invalidates CloudFront.

Credentials are read from the environment. In GitHub Actions, the OIDC step
injects AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, and AWS_SESSION_TOKEN.
Locally, a configured AWS profile is used.

CloudFront invalidation is performed only when CLOUDFRONT_DISTRIBUTION_ID
is set in the environment.
"""
import argparse
import os
import sys
from pathlib import Path

import boto3

REPO_ROOT = Path(__file__).parent.parent
DEFAULT_BUILD_DIR = REPO_ROOT / "build"
DEFAULT_BUCKET = "prates-fyi-news"

_CONTENT_TYPES: dict = {
    ".html": "text/html; charset=utf-8",
    ".css":  "text/css; charset=utf-8",
    ".js":   "application/javascript",
    ".png":  "image/png",
    ".jpg":  "image/jpeg",
    ".svg":  "image/svg+xml",
    ".ico":  "image/x-icon",
    ".woff2": "font/woff2",
    ".woff":  "font/woff",
}


def upload_dir(build_dir: Path, bucket: str) -> int:
    s3 = boto3.client("s3")
    count = 0
    for file_path in sorted(build_dir.rglob("*")):
        if not file_path.is_file():
            continue
        key = str(file_path.relative_to(build_dir))
        content_type = _CONTENT_TYPES.get(file_path.suffix, "application/octet-stream")
        s3.put_object(
            Bucket=bucket,
            Key=key,
            Body=file_path.read_bytes(),
            ContentType=content_type,
        )
        print(f"  ↑ {key}", file=sys.stderr)
        count += 1
    return count


def invalidate_cloudfront(distribution_id: str) -> None:
    cf = boto3.client("cloudfront")
    cf.create_invalidation(
        DistributionId=distribution_id,
        InvalidationBatch={
            "Paths": {"Quantity": 1, "Items": ["/*", "/"]},
            "CallerReference": str(os.getpid()),
        },
    )
    print(f"✓ CloudFront invalidation created for {distribution_id}", file=sys.stderr)


def deploy(build_dir: Path = DEFAULT_BUILD_DIR, bucket: str = DEFAULT_BUCKET) -> None:
    if os.environ.get("ENV") != "prod":
        print("Skipping S3 upload (ENV != prod)", file=sys.stderr)
        return

    count = upload_dir(build_dir, bucket)
    print(f"✓ Uploaded {count} files to s3://{bucket}", file=sys.stderr)

    dist_id = os.environ.get("CLOUDFRONT_DISTRIBUTION_ID")
    if dist_id:
        invalidate_cloudfront(dist_id)


def main() -> None:
    parser = argparse.ArgumentParser(description="Upload build/ to S3")
    parser.add_argument("--build-dir", default=str(DEFAULT_BUILD_DIR))
    parser.add_argument("--bucket", default=DEFAULT_BUCKET)
    args = parser.parse_args()
    deploy(build_dir=Path(args.build_dir), bucket=args.bucket)


if __name__ == "__main__":
    main()
