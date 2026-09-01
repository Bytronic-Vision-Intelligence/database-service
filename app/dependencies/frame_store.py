"""Persist captured frames as files plus a metadata row.

The JPEG goes to disk and only its path is recorded, so the .db stays small
enough to copy around and retention becomes a file sweep rather than a VACUUM.

Note on the DDL below: SqliteDatabaseActions.create_table() cannot be used. It
tries to parameterise a table name (`CREATE TABLE ?`, which SQLite does not
allow), calls list.append() with two arguments, and raises self.connection - a
Connection object, not an exception. Its own docstring says it is
non-functional. Repairing it is a separate chore; this module owns explicit DDL
instead.
"""

from __future__ import annotations

import base64
import binascii
import sqlite3
from pathlib import Path
from uuid import uuid4

_DDL = """
CREATE TABLE IF NOT EXISTS {table} (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    ts         TEXT    NOT NULL,
    camera_id  TEXT    NOT NULL,
    path       TEXT    NOT NULL,
    width      INTEGER,
    height     INTEGER,
    bytes      INTEGER,
    note       TEXT
)
"""


def ensure_table(connection, table: str = "frames") -> None:
    """Create the frames table and its index if absent.

    Safe to call on every boot. Unlike the sku_table guard in main(), a missing
    frames table is created rather than fatal.
    """
    connection.execute(_DDL.format(table=table))
    connection.execute(f"CREATE INDEX IF NOT EXISTS idx_{table}_ts ON {table}(ts)")
    connection.commit()


def _decode_jpeg(image_b64) -> bytes:
    """Decode base64 JPEG bytes, rejecting anything that is not an image.

    Raises:
        ValueError: the payload is not valid base64, or does not start with the
            JPEG SOI marker. A caller could base64 anything; only JPEG belongs
            in the image store.
    """
    try:
        data = base64.b64decode(str(image_b64), validate=True)
    except (binascii.Error, TypeError, ValueError) as exc:
        raise ValueError(f"Frame image is not valid base64: {exc}") from exc
    if not data.startswith(b"\xff\xd8"):
        raise ValueError("Frame image is not JPEG data")
    return data


def _relative_path(ts: str, camera_id: str) -> Path:
    """Build a day-foldered, collision-free relative path for a frame.

    The uuid suffix matters: the camera stamps whole seconds, so a burst or two
    quick saves would otherwise write the same filename twice and the first
    frame would be silently lost.
    """
    stamp = ts.replace("-", "").replace(":", "").replace(" ", "_") or "unstamped"
    day = stamp.split("_")[0] or "unstamped"
    return Path(day) / f"{stamp}_{camera_id}_{uuid4().hex[:8]}.jpg"


def save_frame(
    payload: dict,
    *,
    image_store: Path,
    connection,
    table: str = "frames",
) -> dict:
    """Write a frame to disk and record it in the database.

    Args:
        payload: the MQTT save_frame message - camera_id, image (base64 JPEG),
            date_time.
        image_store: root directory for stored frames.
        connection: an open sqlite3 connection.
        table: metadata table name.
    Returns:
        {"ok": True, "id": <row id>, "path": <path relative to image_store>}
    Raises:
        ValueError: the payload does not carry a decodable JPEG.
        sqlite3.Error: the insert failed - the written file is removed first.
    """
    camera_id = str(payload.get("camera_id") or "unknown")
    ts = str(payload.get("date_time") or "")
    data = _decode_jpeg(payload.get("image"))

    relative = _relative_path(ts, camera_id)
    target = Path(image_store) / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)

    try:
        cursor = connection.execute(
            f"INSERT INTO {table} (ts, camera_id, path, bytes) VALUES (?, ?, ?, ?)",
            (ts, camera_id, str(relative), len(data)),
        )
        connection.commit()
    except sqlite3.Error:
        # Never leave an image with no row pointing at it.
        target.unlink(missing_ok=True)
        raise

    return {"ok": True, "id": int(cursor.lastrowid), "path": str(relative)}
