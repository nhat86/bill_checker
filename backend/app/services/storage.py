"""Object storage abstraction: MinIO (S3-compatible) or local filesystem.

Storage backends are only ever addressed by opaque object keys — no public URLs.
Receipts/product photos are private user data.
"""

import io
from functools import lru_cache
from pathlib import Path

from app.core.config import settings


class StorageBackend:
    def put(self, key: str, data: bytes, content_type: str | None = None) -> str: ...
    def get(self, key: str) -> bytes: ...


class FilesystemStorage(StorageBackend):
    def __init__(self, root: str) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        # prevent path traversal
        safe = Path(*[p for p in Path(key).parts if p not in ("..", "/", "\\")])
        return self.root / safe

    def put(self, key: str, data: bytes, content_type: str | None = None) -> str:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return key

    def get(self, key: str) -> bytes:
        return self._path(key).read_bytes()


class MinioStorage(StorageBackend):
    def __init__(self) -> None:
        from minio import Minio
        from urllib3.util import parse_url

        parsed = parse_url(settings.s3_endpoint)
        secure = parsed.scheme == "https"
        self.bucket = settings.s3_bucket
        self.client = Minio(
            parsed.host + (f":{parsed.port}" if parsed.port else ""),
            access_key=settings.s3_access_key,
            secret_key=settings.s3_secret_key,
            secure=secure,
        )
        if not self.client.bucket_exists(self.bucket):
            self.client.make_bucket(self.bucket)

    def put(self, key: str, data: bytes, content_type: str | None = None) -> str:
        self.client.put_object(
            self.bucket, key, io.BytesIO(data), len(data), content_type=content_type or "application/octet-stream"
        )
        return key

    def get(self, key: str) -> bytes:
        resp = self.client.get_object(self.bucket, key)
        try:
            return resp.read()
        finally:
            resp.close()
            resp.release_conn()


@lru_cache
def get_storage() -> StorageBackend:
    if settings.storage_backend == "minio":
        return MinioStorage()
    return FilesystemStorage(settings.local_storage_dir)
