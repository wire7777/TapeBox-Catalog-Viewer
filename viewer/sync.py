import fcntl
import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import requests


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"

CATALOG_PATH = DATA_DIR / "catalog.db"
NEW_CATALOG_PATH = DATA_DIR / "catalog.new.db"
STATUS_PATH = DATA_DIR / "sync-status.json"
LOCK_PATH = DATA_DIR / "sync.lock"
API_KEY_PATH = DATA_DIR / "mirror-api-key"

from viewer.settings import get_catalog_url


def _utc_now():
    return datetime.now(
        timezone.utc
    ).isoformat()


def _write_status(status):
    DATA_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    temp_path = STATUS_PATH.with_suffix(
        ".json.tmp"
    )

    temp_path.write_text(
        json.dumps(
            status,
            indent=2,
        )
    )

    os.replace(
        temp_path,
        STATUS_PATH,
    )


def get_sync_status():
    if not STATUS_PATH.is_file():
        return {
            "last_attempt": None,
            "last_success": None,
            "success": None,
            "error": None,
            "catalog_size_bytes": None,
            "tape_count": None,
            "file_count": None,
        }

    try:
        return json.loads(
            STATUS_PATH.read_text()
        )

    except Exception:
        return {
            "last_attempt": None,
            "last_success": None,
            "success": None,
            "error": (
                "Sync status file could not be read."
            ),
            "catalog_size_bytes": None,
            "tape_count": None,
            "file_count": None,
        }


def _validate_catalog(path):
    db = sqlite3.connect(
        f"file:{path}?mode=ro&immutable=1",
        uri=True,
    )

    try:
        integrity = db.execute(
            "PRAGMA integrity_check"
        ).fetchone()[0]

        if integrity != "ok":
            raise RuntimeError(
                f"SQLite integrity check failed: "
                f"{integrity}"
            )

        tables = {
            row[0]
            for row in db.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table'
                """
            )
        }

        required = {
            "tapes",
            "files",
        }

        missing = (
            required - tables
        )

        if missing:
            raise RuntimeError(
                "Catalog is missing required tables: "
                + ", ".join(
                    sorted(missing)
                )
            )

        tape_count = db.execute(
            "SELECT COUNT(*) FROM tapes"
        ).fetchone()[0]

        file_count = db.execute(
            "SELECT COUNT(*) FROM files"
        ).fetchone()[0]

        return {
            "integrity": integrity,
            "tape_count": tape_count,
            "file_count": file_count,
        }

    finally:
        db.close()


def _sync_catalog_unlocked():
    DATA_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    catalog_url = get_catalog_url()

    attempt_time = _utc_now()

    previous_status = get_sync_status()

    NEW_CATALOG_PATH.unlink(
        missing_ok=True
    )

    for suffix in ("-wal", "-shm"):
        Path(
            str(NEW_CATALOG_PATH) + suffix
        ).unlink(
            missing_ok=True
        )

    try:
        api_key = ""

        if API_KEY_PATH.is_file():
            api_key = (
                API_KEY_PATH
                .read_text()
                .strip()
            )

        headers = {}

        if api_key:
            headers[
                "X-TapeBox-API-Key"
            ] = api_key

        with requests.get(
            catalog_url,
            headers=headers,
            stream=True,
            timeout=(5, 120),
        ) as response:

            response.raise_for_status()

            if (
                response.headers.get(
                    "X-TapeBox-Catalog-Snapshot"
                )
                != "true"
            ):
                raise RuntimeError(
                    "Server response was not marked "
                    "as a TapeBox catalog snapshot."
                )

            with NEW_CATALOG_PATH.open(
                "wb"
            ) as output:
                for chunk in response.iter_content(
                    chunk_size=1024 * 1024
                ):
                    if chunk:
                        output.write(chunk)

                output.flush()
                os.fsync(
                    output.fileno()
                )

        if (
            not NEW_CATALOG_PATH.is_file()
            or NEW_CATALOG_PATH.stat().st_size == 0
        ):
            raise RuntimeError(
                "Downloaded catalog is empty."
            )

        validation = _validate_catalog(
            NEW_CATALOG_PATH
        )

        catalog_size = (
            NEW_CATALOG_PATH.stat().st_size
        )

        os.replace(
            NEW_CATALOG_PATH,
            CATALOG_PATH,
        )

        success_time = _utc_now()

        status = {
            "success": True,
            "source": catalog_url,
            "last_attempt": attempt_time,
            "last_success": success_time,
            "error": None,
            "catalog_size_bytes": catalog_size,
            "tape_count": validation[
                "tape_count"
            ],
            "file_count": validation[
                "file_count"
            ],
        }

        _write_status(
            status
        )

        return status

    except Exception as exc:
        NEW_CATALOG_PATH.unlink(
            missing_ok=True
        )

        for suffix in ("-wal", "-shm"):
            Path(
                str(NEW_CATALOG_PATH) + suffix
            ).unlink(
                missing_ok=True
            )

        status = {
            "success": False,
            "source": catalog_url,
            "last_attempt": attempt_time,
            "last_success": previous_status.get(
                "last_success"
            ),
            "error": str(exc),
            "catalog_size_bytes": (
                CATALOG_PATH.stat().st_size
                if CATALOG_PATH.is_file()
                else None
            ),
            "tape_count": previous_status.get(
                "tape_count"
            ),
            "file_count": previous_status.get(
                "file_count"
            ),
        }

        _write_status(
            status
        )

        return status



def sync_catalog():
    """
    Synchronize the mirrored catalog.

    A process-wide file lock prevents the web application
    and automatic sync worker from updating the mirror at
    the same time.
    """

    DATA_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    with LOCK_PATH.open(
        "a+"
    ) as lock_file:

        fcntl.flock(
            lock_file.fileno(),
            fcntl.LOCK_EX,
        )

        try:
            return _sync_catalog_unlocked()

        finally:
            fcntl.flock(
                lock_file.fileno(),
                fcntl.LOCK_UN,
            )
