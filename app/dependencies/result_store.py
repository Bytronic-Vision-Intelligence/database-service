"""Persist inference results and link them to the frame they came from.

inference-service never learns the row id database-service gave a frame, so the
two correlate on camera_id plus the camera's timestamp. Resolution runs in both
directions: a result looks for its frame on insert, and storing a frame
back-fills any result that got there first. Inference takes time so the frame
normally lands first, but that is a timing assumption rather than a guarantee.

Explicit DDL for the same reason as frame_store: create_table() in
SqliteDatabaseActions is non-functional.
"""

from __future__ import annotations

import json
import sqlite3

_DDL = """
CREATE TABLE IF NOT EXISTS {table} (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    ts         TEXT    NOT NULL,
    camera_id  TEXT    NOT NULL,
    frame_id   INTEGER,
    model      TEXT,
    detections TEXT    NOT NULL,
    count      INTEGER NOT NULL,
    top_class  TEXT,
    top_conf   REAL,
    FOREIGN KEY (frame_id) REFERENCES frames(id)
)
"""


def ensure_table(connection, table: str = "results") -> None:
    """Create the results table and its indexes if absent.

    Safe to call on every boot; a missing table is created, never fatal.
    """
    connection.execute(_DDL.format(table=table))
    connection.execute(f"CREATE INDEX IF NOT EXISTS idx_{table}_ts ON {table}(ts)")
    connection.execute(
        f"CREATE INDEX IF NOT EXISTS idx_{table}_frame ON {table}(frame_id)"
    )
    connection.commit()


def _summarise(detections: list):
    """Return (count, top class name, top confidence) for the listing columns.

    These are denormalised so the Results page - which uses the generic
    read-only table viewer - shows something readable instead of one JSON blob
    per row. The top detection is the most confident one, not the first.
    """
    if not detections:
        return 0, None, None
    top = max(detections, key=lambda d: float(d.get("confidence") or 0.0))
    return len(detections), top.get("name"), top.get("confidence")


def _resolve_frame_id(connection, *, camera_id: str, ts: str, frames_table: str):
    """Newest stored frame for this camera at this timestamp, or None."""
    try:
        row = connection.execute(
            f"SELECT id FROM {frames_table} WHERE camera_id = ? AND ts = ? "
            f"ORDER BY id DESC LIMIT 1",
            (camera_id, ts),
        ).fetchone()
    except sqlite3.Error:
        # No frames table yet is not a reason to lose the result.
        return None
    return int(row[0]) if row else None


def save_result(
    payload: dict,
    *,
    connection,
    table: str = "results",
    frames_table: str = "frames",
) -> dict:
    """Store an inference result, linking it to its frame when one exists.

    Args:
        payload: the MQTT save_result message - camera_id, date_time, model,
            detections.
        connection: an open sqlite3 connection.
        table: results table name.
        frames_table: frames table name, used to resolve the link.
    Returns:
        {"ok": True, "id": <row id>, "frame_id": <int or None>}
    Raises:
        ValueError: `detections` is missing or is not a list.
    """
    detections = payload.get("detections")
    if not isinstance(detections, list):
        raise ValueError("Result payload 'detections' must be a list")

    camera_id = str(payload.get("camera_id") or "unknown")
    ts = str(payload.get("date_time") or "")
    model = str(payload.get("model") or "")
    count, top_class, top_conf = _summarise(detections)
    frame_id = _resolve_frame_id(
        connection, camera_id=camera_id, ts=ts, frames_table=frames_table
    )

    cursor = connection.execute(
        f"INSERT INTO {table} "
        f"(ts, camera_id, frame_id, model, detections, count, top_class, top_conf) "
        f"VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            ts,
            camera_id,
            frame_id,
            model,
            json.dumps(detections),
            count,
            top_class,
            top_conf,
        ),
    )
    connection.commit()
    return {"ok": True, "id": int(cursor.lastrowid), "frame_id": frame_id}


def backfill_frame_id(
    connection,
    *,
    camera_id: str,
    ts: str,
    frame_id: int,
    table: str = "results",
) -> int:
    """Link results stored before their frame existed.

    Only fills nulls, so a link resolved at insert time is never overwritten.

    Returns:
        how many rows were updated.
    """
    cursor = connection.execute(
        f"UPDATE {table} SET frame_id = ? "
        f"WHERE camera_id = ? AND ts = ? AND frame_id IS NULL",
        (frame_id, camera_id, ts),
    )
    connection.commit()
    return int(cursor.rowcount or 0)
