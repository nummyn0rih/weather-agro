"""Yandex.Disk WebDAV client (task 6.2).

Thin async wrapper around the Yandex.Disk WebDAV endpoint at
``https://webdav.yandex.ru``. Supports:

* ``ensure_dir`` — recursive ``MKCOL`` for the target backup root.
* ``upload`` — ``PUT`` a local file (streamed) to a remote path.
* ``download`` — ``GET`` a remote object into a local file (streamed).
* ``list_dir`` — ``PROPFIND`` (Depth=1) returning child entries.
* ``delete`` — ``DELETE`` a remote object.

Authentication is HTTP Basic with the Yandex login + an **app password**
(generated at passport.yandex.ru → "Пароли приложений"). The standard
account password does not work.

Credentials are resolved through :mod:`app.services.settings.resolver`
(DB override wins; falls back to env). Construct via :func:`build_client`
inside an async context.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import IO

import httpx
import structlog
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.core.config import get_settings
from app.services.settings import resolver as settings_resolver

logger = structlog.get_logger(__name__)

WEBDAV_BASE_URL = "https://webdav.yandex.ru"
_DAV_NS = "DAV:"


class YandexDiskError(RuntimeError):
    """Raised for non-recoverable Yandex.Disk WebDAV failures."""


@dataclass(frozen=True)
class RemoteEntry:
    """One PROPFIND result row."""

    name: str
    path: str
    size: int
    is_dir: bool


def _normalize_dir(path: str) -> str:
    if not path.startswith("/"):
        path = "/" + path
    if not path.endswith("/"):
        path = path + "/"
    return path


def _join(root: str, name: str) -> str:
    return _normalize_dir(root) + name.lstrip("/")


class YandexDiskClient:
    """Async WebDAV client for Yandex.Disk.

    Use :func:`build_client` instead of constructing directly so credentials
    are loaded from the settings resolver.
    """

    def __init__(
        self,
        *,
        login: str,
        app_password: str,
        backup_root: str,
        client: httpx.AsyncClient,
    ) -> None:
        self._login = login
        self._client = client
        self._backup_root = _normalize_dir(backup_root)
        self._auth = httpx.BasicAuth(login, app_password)

    @property
    def backup_root(self) -> str:
        return self._backup_root

    async def ensure_dir(self, path: str) -> None:
        """Create ``path`` (and missing parents) on Yandex.Disk.

        Yandex's WebDAV does not support recursive ``MKCOL`` — walk parents
        and call ``MKCOL`` per segment, ignoring 405 (already exists).
        """
        path = _normalize_dir(path)
        parts = [p for p in PurePosixPath(path).parts if p != "/"]
        current = ""
        for part in parts:
            current = current + "/" + part
            await self._mkcol(current + "/")

    async def _mkcol(self, path: str) -> None:
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=1, max=10),
            retry=retry_if_exception_type(httpx.TransportError),
            reraise=True,
        ):
            with attempt:
                resp = await self._client.request(
                    "MKCOL",
                    WEBDAV_BASE_URL + path,
                    auth=self._auth,
                )
        # 201 created, 405 already exists, 409 missing parent → real error.
        if resp.status_code in (201, 405):
            return
        raise YandexDiskError(
            f"MKCOL {path} failed: {resp.status_code} {resp.text[:200]}"
        )

    async def upload(self, local_path: str, remote_path: str) -> int:
        """Stream ``local_path`` to ``remote_path``. Returns bytes uploaded."""
        size = 0

        async def _attempt() -> httpx.Response:
            with open(local_path, "rb") as f:
                return await self._client.put(
                    WEBDAV_BASE_URL + remote_path,
                    content=_iter_file(f),
                    auth=self._auth,
                    headers={"Expect": "100-continue"},
                    timeout=httpx.Timeout(connect=30.0, read=300.0, write=300.0, pool=30.0),
                )

        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=2, max=30),
            retry=retry_if_exception_type(httpx.TransportError),
            reraise=True,
        ):
            with attempt:
                resp = await _attempt()
        if resp.status_code not in (200, 201, 204):
            raise YandexDiskError(
                f"PUT {remote_path} failed: {resp.status_code} {resp.text[:200]}"
            )
        # Re-stat the file to learn size (cheaper than streaming-count).
        import os

        size = os.path.getsize(local_path)
        logger.info(
            "yandex_disk.uploaded",
            remote_path=remote_path,
            size_bytes=size,
        )
        return size

    async def download(self, remote_path: str, local_path: str) -> int:
        """Stream ``remote_path`` to ``local_path``. Returns bytes written."""
        total = 0
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=2, max=30),
            retry=retry_if_exception_type(httpx.TransportError),
            reraise=True,
        ):
            with attempt:
                async with self._client.stream(
                    "GET",
                    WEBDAV_BASE_URL + remote_path,
                    auth=self._auth,
                    timeout=httpx.Timeout(connect=30.0, read=300.0, write=300.0, pool=30.0),
                ) as resp:
                    if resp.status_code != 200:
                        body = await resp.aread()
                        raise YandexDiskError(
                            f"GET {remote_path} failed: "
                            f"{resp.status_code} {body[:200]!r}"
                        )
                    total = 0
                    with open(local_path, "wb") as f:
                        async for chunk in resp.aiter_bytes(chunk_size=64 * 1024):
                            f.write(chunk)
                            total += len(chunk)
        logger.info(
            "yandex_disk.downloaded",
            remote_path=remote_path,
            size_bytes=total,
        )
        return total

    async def list_dir(self, path: str) -> list[RemoteEntry]:
        """Return child entries of ``path`` (Depth=1, excluding the dir itself)."""
        path = _normalize_dir(path)
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=1, max=10),
            retry=retry_if_exception_type(httpx.TransportError),
            reraise=True,
        ):
            with attempt:
                resp = await self._client.request(
                    "PROPFIND",
                    WEBDAV_BASE_URL + path,
                    auth=self._auth,
                    headers={"Depth": "1"},
                )
        if resp.status_code == 404:
            return []
        if resp.status_code not in (207, 200):
            raise YandexDiskError(
                f"PROPFIND {path} failed: {resp.status_code} {resp.text[:200]}"
            )
        return _parse_propfind(resp.text, parent=path)

    async def delete(self, remote_path: str) -> None:
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=1, max=10),
            retry=retry_if_exception_type(httpx.TransportError),
            reraise=True,
        ):
            with attempt:
                resp = await self._client.request(
                    "DELETE",
                    WEBDAV_BASE_URL + remote_path,
                    auth=self._auth,
                )
        if resp.status_code not in (200, 204, 404):
            raise YandexDiskError(
                f"DELETE {remote_path} failed: {resp.status_code} {resp.text[:200]}"
            )
        logger.info("yandex_disk.deleted", remote_path=remote_path)

    def join(self, *parts: str) -> str:
        """Build an absolute remote path under the backup root."""
        path = self._backup_root.rstrip("/")
        for part in parts:
            path = path + "/" + part.strip("/")
        return path


def _iter_file(fh: IO[bytes], chunk_size: int = 1024 * 1024):
    while True:
        chunk = fh.read(chunk_size)
        if not chunk:
            break
        yield chunk


def _parse_propfind(xml_body: str, parent: str) -> list[RemoteEntry]:
    """Parse a Yandex.Disk PROPFIND multistatus XML into RemoteEntry rows.

    Excludes the parent collection itself.
    """
    parent_norm = _normalize_dir(parent)
    results: list[RemoteEntry] = []
    root = ET.fromstring(xml_body)
    for resp in root.findall(f"{{{_DAV_NS}}}response"):
        href_el = resp.find(f"{{{_DAV_NS}}}href")
        if href_el is None or not href_el.text:
            continue
        href = httpx.URL(href_el.text).path
        # Skip the parent collection itself.
        if href == parent_norm or href + "/" == parent_norm:
            continue
        is_dir = (
            resp.find(
                f"{{{_DAV_NS}}}propstat/{{{_DAV_NS}}}prop/"
                f"{{{_DAV_NS}}}resourcetype/{{{_DAV_NS}}}collection"
            )
            is not None
        )
        size_el = resp.find(
            f"{{{_DAV_NS}}}propstat/{{{_DAV_NS}}}prop/"
            f"{{{_DAV_NS}}}getcontentlength"
        )
        size = int(size_el.text) if (size_el is not None and size_el.text) else 0
        name = PurePosixPath(href.rstrip("/")).name
        results.append(
            RemoteEntry(name=name, path=href, size=size, is_dir=is_dir)
        )
    return results


async def _resolve_credentials() -> tuple[str, str]:
    login = await settings_resolver.get_secret("yandex_disk_login")
    password = await settings_resolver.get_secret("yandex_disk_app_password")
    if not login or not password:
        raise YandexDiskError(
            "Yandex.Disk credentials are not configured "
            "(set YANDEX_DISK_LOGIN and YANDEX_DISK_APP_PASSWORD)"
        )
    return login, password


@asynccontextmanager
async def build_client() -> AsyncIterator[YandexDiskClient]:
    """Create a :class:`YandexDiskClient` with credentials resolved from DB/env."""
    login, password = await _resolve_credentials()
    backup_root = get_settings().YANDEX_DISK_BACKUP_PATH
    async with httpx.AsyncClient(
        timeout=httpx.Timeout(connect=30.0, read=60.0, write=60.0, pool=30.0),
    ) as client:
        yield YandexDiskClient(
            login=login,
            app_password=password,
            backup_root=backup_root,
            client=client,
        )
