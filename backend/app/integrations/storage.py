"""Хранилище документов: локальный диск (по умолчанию) или S3-совместимое (MinIO)."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Protocol

from app.core.config import get_settings


class Storage(Protocol):
    async def put(self, key: str, data: bytes, content_type: str) -> None: ...
    async def get(self, key: str) -> bytes: ...
    async def delete(self, key: str) -> None: ...
    async def ping(self) -> bool: ...


class LocalStorage:
    def __init__(self, root: str) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        p = (self.root / key).resolve()
        if self.root.resolve() not in p.parents:
            raise ValueError("invalid storage key")
        return p

    async def put(self, key: str, data: bytes, content_type: str) -> None:
        p = self._path(key)
        await asyncio.to_thread(p.parent.mkdir, parents=True, exist_ok=True)
        await asyncio.to_thread(p.write_bytes, data)

    async def get(self, key: str) -> bytes:
        return await asyncio.to_thread(self._path(key).read_bytes)

    async def delete(self, key: str) -> None:
        p = self._path(key)
        await asyncio.to_thread(lambda: p.unlink(missing_ok=True))

    async def ping(self) -> bool:
        return self.root.exists()


class S3Storage:
    def __init__(self) -> None:
        import aioboto3  # опциональная зависимость (extra «s3»)

        s = get_settings()
        self.bucket = s.s3_bucket
        self._session = aioboto3.Session(
            aws_access_key_id=s.s3_access_key, aws_secret_access_key=s.s3_secret_key
        )
        self._endpoint = s.s3_endpoint

    def _client(self):  # noqa: ANN202
        return self._session.client("s3", endpoint_url=self._endpoint)

    async def put(self, key: str, data: bytes, content_type: str) -> None:
        async with self._client() as c:
            await c.put_object(Bucket=self.bucket, Key=key, Body=data, ContentType=content_type)

    async def get(self, key: str) -> bytes:
        async with self._client() as c:
            obj = await c.get_object(Bucket=self.bucket, Key=key)
            return await obj["Body"].read()

    async def delete(self, key: str) -> None:
        async with self._client() as c:
            await c.delete_object(Bucket=self.bucket, Key=key)

    async def ping(self) -> bool:
        try:
            async with self._client() as c:
                await c.head_bucket(Bucket=self.bucket)
            return True
        except Exception:  # noqa: BLE001
            return False


_storage: Storage | None = None


def get_storage() -> Storage:
    global _storage
    if _storage is None:
        s = get_settings()
        _storage = S3Storage() if s.storage_backend == "s3" else LocalStorage(s.storage_dir)
    return _storage


def reset_storage() -> None:
    global _storage
    _storage = None
