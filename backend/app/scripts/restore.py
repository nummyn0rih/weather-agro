"""Restore the database from a Yandex.Disk backup (task 6.2).

Downloads a ``weather_*.sql.gz`` archive from Yandex.Disk, decompresses
it, and pipes the SQL into ``psql`` against the live database. This is
a **destructive** operation — it will execute the dump's `DROP TABLE` /
`CREATE TABLE` statements over the existing schema.

Usage::

    # Restore from a specific remote path (full path under WebDAV)
    docker compose exec backend python -m app.scripts.restore \\
        --remote /weather-app-backups/daily/weather_2026-05-12_040000.sql.gz

    # Or by filename — script searches daily/ first, then monthly/
    docker compose exec backend python -m app.scripts.restore \\
        --name weather_2026-05-12_040000.sql.gz

    # List available backups (no restore)
    docker compose exec backend python -m app.scripts.restore --list

Requires ``psql`` and ``gunzip`` to be available in ``PATH``.
"""
from __future__ import annotations

import argparse
import asyncio
import os
import subprocess
import sys
import tempfile

import structlog

from app.core.logging import configure_logging
from app.db.session import engine
from app.services.backup.runner import _parse_database_url, list_remote_backups
from app.services.backup.yandex_disk import YandexDiskError, build_client

logger = structlog.get_logger(__name__)


def _confirm(prompt: str) -> bool:
    try:
        return input(prompt + " [y/N] ").strip().lower() in {"y", "yes"}
    except EOFError:
        return False


async def _resolve_remote_path(name: str | None, remote: str | None) -> str:
    if remote:
        return remote
    if not name:
        raise SystemExit("either --remote or --name is required")
    async with build_client() as client:
        for subdir in ("daily", "monthly"):
            entries = await client.list_dir(client.join(subdir) + "/")
            for e in entries:
                if e.name == name:
                    return e.path
    raise SystemExit(f"no archive matching {name!r} found on Yandex.Disk")


async def _do_list() -> int:
    items = await list_remote_backups()
    if not items:
        print("(no backups found)")
        return 0
    for it in items:
        size_mb = it.size_bytes / (1024 * 1024)
        print(f"[{it.kind:8s}] {it.name}  ({size_mb:7.2f} MiB)  {it.path}")
    return 0


def _psql_restore(local_sql: str) -> None:
    """Execute SQL from ``local_sql`` against the configured database."""
    from app.core.config import get_settings

    conn = _parse_database_url(get_settings().DATABASE_URL)
    env = os.environ.copy()
    env["PGPASSWORD"] = conn.password
    logger.info(
        "restore.psql_start",
        host=conn.host,
        database=conn.database,
        file=local_sql,
    )
    result = subprocess.run(
        [
            "psql",
            "--host", conn.host,
            "--port", str(conn.port),
            "--username", conn.user,
            "--no-password",
            "--dbname", conn.database,
            "--file", local_sql,
            "--single-transaction",
            "--set", "ON_ERROR_STOP=on",
        ],
        env=env,
        check=False,
    )
    if result.returncode != 0:
        raise SystemExit(f"psql restore failed with exit code {result.returncode}")
    logger.info("restore.psql_done", file=local_sql)


async def _do_restore(args: argparse.Namespace) -> int:
    remote_path = await _resolve_remote_path(args.name, args.remote)

    if not args.yes:
        print(f"About to RESTORE the database from: {remote_path}")
        print("This will overwrite the current database. There is no undo.")
        if not _confirm("Proceed?"):
            print("Cancelled.")
            return 1

    with tempfile.TemporaryDirectory(prefix="weather-restore-") as tmpdir:
        gz_path = os.path.join(tmpdir, "backup.sql.gz")
        sql_path = os.path.join(tmpdir, "backup.sql")
        try:
            async with build_client() as client:
                await client.download(remote_path, gz_path)
        except YandexDiskError as exc:
            raise SystemExit(f"download failed: {exc}") from exc

        # Decompress with system gunzip — keeps the temp tree streaming-friendly
        # for large dumps.
        gz = subprocess.run(["gunzip", "-c", gz_path], stdout=open(sql_path, "wb"))
        if gz.returncode != 0:
            raise SystemExit(f"gunzip failed with exit code {gz.returncode}")

        _psql_restore(sql_path)

    print(f"Restore from {remote_path} completed.")
    return 0


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="restore", description=__doc__)
    p.add_argument(
        "--remote", help="Full WebDAV path of the archive to restore"
    )
    p.add_argument(
        "--name",
        help="Archive filename (searched under daily/ then monthly/)",
    )
    p.add_argument(
        "--list",
        action="store_true",
        help="List available backups on Yandex.Disk and exit",
    )
    p.add_argument(
        "--yes",
        action="store_true",
        help="Skip the interactive confirmation prompt",
    )
    return p.parse_args()


async def _main() -> int:
    configure_logging()
    args = _parse_args()
    try:
        if args.list:
            return await _do_list()
        return await _do_restore(args)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    sys.exit(asyncio.run(_main()))
