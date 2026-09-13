import sqlite3
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
CATALOG_PATH = BASE_DIR / "data" / "catalog.db"


def _connect():
    if not CATALOG_PATH.is_file():
        raise FileNotFoundError(
            "Catalog mirror has not been synchronized yet."
        )

    db = sqlite3.connect(
        f"file:{CATALOG_PATH}?mode=ro&immutable=1",
        uri=True,
    )

    db.row_factory = sqlite3.Row

    return db


def list_files():
    db = _connect()

    try:
        rows = db.execute(
            """
            SELECT
                f.id,
                f.filename,
                f.original_path,
                f.relative_path,
                f.size_bytes,
                f.checksum_sha256,
                f.tape_path,
                f.is_spanned,
                f.original_created_at,
                f.original_modified_at,
                f.archived_at,
                f.tape_id,
                t.label AS tape_label,
                t.barcode AS tape_barcode
            FROM files AS f
            LEFT JOIN tapes AS t
                ON t.id = f.tape_id
            ORDER BY
                LOWER(f.relative_path),
                LOWER(f.filename)
            """
        ).fetchall()

        return [
            dict(row)
            for row in rows
        ]

    finally:
        db.close()


def search_files(query):
    query = (
        query or ""
    ).strip()

    if not query:
        return list_files()

    pattern = f"%{query}%"

    db = _connect()

    try:
        rows = db.execute(
            """
            SELECT
                f.id,
                f.filename,
                f.original_path,
                f.relative_path,
                f.size_bytes,
                f.checksum_sha256,
                f.tape_path,
                f.is_spanned,
                f.original_created_at,
                f.original_modified_at,
                f.archived_at,
                f.tape_id,
                t.label AS tape_label,
                t.barcode AS tape_barcode
            FROM files AS f
            LEFT JOIN tapes AS t
                ON t.id = f.tape_id
            WHERE
                f.filename LIKE ?
                OR f.original_path LIKE ?
                OR f.relative_path LIKE ?
                OR f.tape_path LIKE ?
            ORDER BY
                LOWER(f.relative_path),
                LOWER(f.filename)
            """
            ,
            (
                pattern,
                pattern,
                pattern,
                pattern,
            ),
        ).fetchall()

        return [
            dict(row)
            for row in rows
        ]

    finally:
        db.close()


def get_file_parts(file_ids):
    file_ids = [
        int(file_id)
        for file_id in file_ids
    ]

    if not file_ids:
        return {}

    placeholders = ",".join(
        "?"
        for _ in file_ids
    )

    db = _connect()

    try:
        rows = db.execute(
            f"""
            SELECT
                p.file_id,
                p.part_number,
                p.tape_id,
                p.tape_path,
                p.size_bytes,
                p.checksum_sha256,
                t.label AS tape_label,
                t.barcode AS tape_barcode
            FROM file_parts AS p
            LEFT JOIN tapes AS t
                ON t.id = p.tape_id
            WHERE p.file_id IN (
                {placeholders}
            )
            ORDER BY
                p.file_id,
                p.part_number
            """,
            file_ids,
        ).fetchall()

        result = {}

        for row in rows:
            item = dict(row)

            result.setdefault(
                item["file_id"],
                [],
            ).append(
                item
            )

        return result

    finally:
        db.close()



def list_tapes():
    db = _connect()

    try:
        rows = db.execute(
            """
            SELECT
                t.id,
                t.label,
                t.barcode,
                t.ltfs_uuid,
                t.generation,
                t.capacity_bytes,
                t.used_bytes,
                t.status,
                t.created_at,

                COUNT(
                    DISTINCT f.id
                ) AS file_count,

                COUNT(
                    DISTINCT p.id
                ) AS part_count

            FROM tapes AS t

            LEFT JOIN files AS f
                ON f.tape_id = t.id

            LEFT JOIN file_parts AS p
                ON p.tape_id = t.id

            GROUP BY
                t.id,
                t.label,
                t.barcode,
                t.ltfs_uuid,
                t.generation,
                t.capacity_bytes,
                t.used_bytes,
                t.status,
                t.created_at

            ORDER BY
                LOWER(t.label)
            """
        ).fetchall()

        return [
            dict(row)
            for row in rows
        ]

    finally:
        db.close()


def get_tape(tape_id):
    db = _connect()

    try:
        row = db.execute(
            """
            SELECT
                id,
                label,
                barcode,
                ltfs_uuid,
                generation,
                capacity_bytes,
                used_bytes,
                status,
                created_at,
                last_seen_at,
                notes,
                friendly_name,
                location
            FROM tapes
            WHERE id = ?
            """,
            (int(tape_id),),
        ).fetchone()

        if row is None:
            return None

        return dict(row)

    finally:
        db.close()


def list_files_for_tape(tape_id):
    db = _connect()

    try:
        rows = db.execute(
            """
            SELECT
                f.id,
                f.filename,
                f.original_path,
                f.relative_path,
                f.size_bytes,
                f.checksum_sha256,
                f.tape_path,
                f.is_spanned,
                f.archived_at
            FROM files AS f
            WHERE f.tape_id = ?

            UNION

            SELECT
                f.id,
                f.filename,
                f.original_path,
                f.relative_path,
                f.size_bytes,
                f.checksum_sha256,
                f.tape_path,
                f.is_spanned,
                f.archived_at
            FROM files AS f
            INNER JOIN file_parts AS p
                ON p.file_id = f.id
            WHERE p.tape_id = ?

            ORDER BY
                relative_path,
                filename
            """,
            (
                int(tape_id),
                int(tape_id),
            ),
        ).fetchall()

        return [
            dict(row)
            for row in rows
        ]

    finally:
        db.close()


def get_file(file_id):
    db = _connect()

    try:
        row = db.execute(
            """
            SELECT
                f.id,
                f.filename,
                f.original_path,
                f.relative_path,
                f.size_bytes,
                f.checksum_sha256,
                f.tape_path,
                f.is_spanned,
                f.original_created_at,
                f.original_modified_at,
                f.archived_at,
                f.tape_id,
                t.label AS tape_label,
                t.barcode AS tape_barcode
            FROM files AS f
            LEFT JOIN tapes AS t
                ON t.id = f.tape_id
            WHERE f.id = ?
            """,
            (int(file_id),),
        ).fetchone()

        if row is None:
            return None

        result = dict(row)

        parts = db.execute(
            """
            SELECT
                p.id,
                p.file_id,
                p.part_number,
                p.tape_id,
                p.tape_path,
                p.size_bytes,
                p.checksum_sha256,
                t.label AS tape_label,
                t.barcode AS tape_barcode
            FROM file_parts AS p
            LEFT JOIN tapes AS t
                ON t.id = p.tape_id
            WHERE p.file_id = ?
            ORDER BY p.part_number
            """,
            (int(file_id),),
        ).fetchall()

        result["parts"] = [
            dict(part)
            for part in parts
        ]

        return result

    finally:
        db.close()


def get_catalog_stats():
    db = _connect()

    try:
        summary = db.execute(
            """
            SELECT
                (
                    SELECT COUNT(*)
                    FROM tapes
                ) AS tape_count,

                (
                    SELECT COUNT(*)
                    FROM files
                ) AS file_count,

                (
                    SELECT COALESCE(
                        SUM(size_bytes),
                        0
                    )
                    FROM files
                ) AS logical_bytes,

                (
                    SELECT COUNT(*)
                    FROM files
                    WHERE is_spanned = 1
                ) AS spanned_file_count,

                (
                    SELECT COALESCE(
                        SUM(used_bytes),
                        0
                    )
                    FROM tapes
                ) AS tape_used_bytes,

                (
                    SELECT COALESCE(
                        SUM(capacity_bytes),
                        0
                    )
                    FROM tapes
                ) AS tape_capacity_bytes
            """
        ).fetchone()

        result = dict(summary)

        result["tape_free_bytes"] = max(
            0,
            result["tape_capacity_bytes"]
            - result["tape_used_bytes"],
        )

        if result["tape_capacity_bytes"] > 0:
            result["utilization_percent"] = (
                result["tape_used_bytes"]
                / result["tape_capacity_bytes"]
                * 100
            )
        else:
            result["utilization_percent"] = 0.0

        generations = db.execute(
            """
            SELECT
                COALESCE(
                    CAST(generation AS TEXT),
                    'Unknown'
                ) AS generation,
                COUNT(*) AS tape_count,
                COALESCE(
                    SUM(used_bytes),
                    0
                ) AS used_bytes,
                COALESCE(
                    SUM(capacity_bytes),
                    0
                ) AS capacity_bytes
            FROM tapes
            GROUP BY
                generation
            ORDER BY
                generation
            """
        ).fetchall()

        statuses = db.execute(
            """
            SELECT
                COALESCE(
                    status,
                    'Unknown'
                ) AS status,
                COUNT(*) AS tape_count
            FROM tapes
            GROUP BY
                status
            ORDER BY
                status
            """
        ).fetchall()

        result["generations"] = [
            dict(row)
            for row in generations
        ]

        result["statuses"] = [
            dict(row)
            for row in statuses
        ]

        return result

    finally:
        db.close()
