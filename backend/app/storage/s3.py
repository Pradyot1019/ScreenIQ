"""Object storage for resume files (S3 API: RustFS locally, R2/S3 in production).

boto3 is synchronous, so calls run in a worker thread (asyncio.to_thread) to keep the
event loop free. Keys are always org-scoped: `orgs/{org_id}/resumes/{resume_id}.pdf`.
"""

import asyncio
from typing import TYPE_CHECKING, Protocol

import boto3
from botocore.config import Config

from app.core.config import get_settings

if TYPE_CHECKING:  # type stubs are a dev dependency; not installed in production
    from mypy_boto3_s3 import S3Client


class Storage(Protocol):
    async def put(self, key: str, data: bytes, content_type: str) -> None: ...
    async def get(self, key: str) -> bytes: ...
    async def signed_url(self, key: str, expires_s: int = 300) -> str: ...


def _client(endpoint: str) -> "S3Client":
    s = get_settings()
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=s.s3_access_key,
        aws_secret_access_key=s.s3_secret_key,
        region_name=s.s3_region,
        # Path-style (host/bucket/key): RustFS needs it, R2 supports it (ADR 0002).
        config=Config(s3={"addressing_style": "path"}, signature_version="s3v4"),
    )


class S3Storage:
    def __init__(self) -> None:
        s = get_settings()
        self.bucket = s.s3_bucket
        self._client = _client(s.s3_endpoint)
        # Signed URLs are opened by the browser, which can't resolve the Docker hostname
        # "rustfs", so they are signed against the public endpoint (ADR 0002).
        self._public = _client(s.s3_public_endpoint or s.s3_endpoint)

    async def put(self, key: str, data: bytes, content_type: str) -> None:
        await asyncio.to_thread(
            self._client.put_object,
            Bucket=self.bucket,
            Key=key,
            Body=data,
            ContentType=content_type,
        )

    async def get(self, key: str) -> bytes:
        obj = await asyncio.to_thread(self._client.get_object, Bucket=self.bucket, Key=key)
        return await asyncio.to_thread(obj["Body"].read)

    async def signed_url(self, key: str, expires_s: int = 300) -> str:
        return await asyncio.to_thread(
            self._public.generate_presigned_url,
            "get_object",
            Params={"Bucket": self.bucket, "Key": key},
            ExpiresIn=expires_s,
        )


_storage: Storage | None = None


def get_storage() -> Storage:
    """FastAPI dependency; tests override it with an in-memory fake."""
    global _storage
    if _storage is None:
        _storage = S3Storage()
    return _storage
