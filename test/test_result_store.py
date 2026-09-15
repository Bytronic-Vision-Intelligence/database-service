"""Storing inference results and linking them to stored frames.

In-memory database throughout, so nothing here touches the real
churchill_database.db.
"""

import json
import sqlite3

import pytest

from dependencies.frame_store import ensure_table as ensure_frames
from dependencies.result_store import backfill_frame_id, ensure_table, save_result

# The real shape, measured against a webcam capture with yolov8n.
DETECTIONS = [
    {"name": "person", "class": 0, "confidence": 0.88423,
     "box": {"x1": 378.35687, "y1": 281.62793, "x2": 1613.9668, "y2": 1080.0}},
    {"name": "chair", "class": 56, "confidence": 0.41,
     "box": {"x1": 0.0, "y1": 0.0, "x2": 10.0, "y2": 10.0}},
]


@pytest.fixture
def conn():
    connection = sqlite3.connect(":memory:")
    ensure_frames(connection)
    ensure_table(connection)
    yield connection
    connection.close()


def _payload(**overrides):
    payload = {
        "command": "save_result",
        "camera_id": "colour_1",
        "date_time": "2026-09-01 14:17:28",
        "model": "yolov8n.pt",
        "detections": DETECTIONS,
    }
    payload.update(overrides)
    return payload


def _insert_frame(conn, *, camera_id="colour_1", ts="2026-09-01 14:17:28"):
    cur = conn.execute(
        "INSERT INTO frames (ts, camera_id, path, bytes) VALUES (?, ?, ?, ?)",
        (ts, camera_id, f"{ts}.jpg", 123),
    )
    conn.commit()
    return cur.lastrowid


def test_ensure_table_is_idempotent(conn):
    ensure_table(conn)
    ensure_table(conn)

    names = [
        r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    ]
    assert names.count("results") == 1


def test_save_result_inserts_a_row(conn):
    out = save_result(_payload(), connection=conn)

    assert out["ok"] is True
    row = conn.execute(
        "SELECT ts, camera_id, model, detections FROM results WHERE id = ?",
        (out["id"],),
    ).fetchone()
    assert row[0] == "2026-09-01 14:17:28"
    assert row[1] == "colour_1"
    assert row[2] == "yolov8n.pt"
    assert json.loads(row[3]) == DETECTIONS


def test_summary_columns_are_denormalised(conn):
    # The Results page uses the generic table viewer, which would otherwise
    # show one unreadable JSON blob per row.
    out = save_result(_payload(), connection=conn)

    row = conn.execute(
        "SELECT count, top_class, top_conf FROM results WHERE id = ?", (out["id"],)
    ).fetchone()
    assert row[0] == 2
    assert row[1] == "person"
    assert row[2] == pytest.approx(0.88423)


def test_top_class_is_the_most_confident_not_the_first(conn):
    # Ordered so the two differ: YOLO does not guarantee confidence order, and
    # a fixture where the first happens to be the best cannot catch this.
    detections = [
        {"name": "chair", "class": 56, "confidence": 0.41, "box": {}},
        {"name": "person", "class": 0, "confidence": 0.97, "box": {}},
    ]

    out = save_result(_payload(detections=detections), connection=conn)

    row = conn.execute(
        "SELECT top_class, top_conf FROM results WHERE id = ?", (out["id"],)
    ).fetchone()
    assert row[0] == "person"
    assert row[1] == pytest.approx(0.97)


def test_an_empty_detection_list_is_recorded(conn):
    # "nothing detected" is a real inspection outcome, not an error.
    out = save_result(_payload(detections=[]), connection=conn)

    row = conn.execute(
        "SELECT count, top_class, top_conf FROM results WHERE id = ?", (out["id"],)
    ).fetchone()
    assert row == (0, None, None)


def test_frame_id_resolves_when_a_matching_frame_exists(conn):
    frame_id = _insert_frame(conn)

    out = save_result(_payload(), connection=conn)

    assert out["frame_id"] == frame_id


def test_frame_id_is_null_when_no_frame_was_stored(conn):
    # A plain Trigger captures without storing; the result is still recorded.
    out = save_result(_payload(), connection=conn)

    assert out["frame_id"] is None


def test_frame_id_does_not_match_a_different_camera(conn):
    _insert_frame(conn, camera_id="thermal_1")

    out = save_result(_payload(), connection=conn)

    assert out["frame_id"] is None


def test_the_newest_frame_wins_when_timestamps_collide(conn):
    _insert_frame(conn)
    newest = _insert_frame(conn)

    out = save_result(_payload(), connection=conn)

    assert out["frame_id"] == newest


def test_backfill_links_a_result_that_arrived_before_its_frame(conn):
    # Inference takes time so the frame usually lands first, but that is a
    # timing assumption, not a guarantee.
    out = save_result(_payload(), connection=conn)
    assert out["frame_id"] is None

    frame_id = _insert_frame(conn)
    linked = backfill_frame_id(
        conn, camera_id="colour_1", ts="2026-09-01 14:17:28", frame_id=frame_id
    )

    assert linked == 1
    row = conn.execute(
        "SELECT frame_id FROM results WHERE id = ?", (out["id"],)
    ).fetchone()
    assert row[0] == frame_id


def test_backfill_never_overwrites_an_existing_link(conn):
    first = _insert_frame(conn)
    out = save_result(_payload(), connection=conn)
    assert out["frame_id"] == first

    linked = backfill_frame_id(
        conn, camera_id="colour_1", ts="2026-09-01 14:17:28", frame_id=999
    )

    assert linked == 0
    row = conn.execute(
        "SELECT frame_id FROM results WHERE id = ?", (out["id"],)
    ).fetchone()
    assert row[0] == first


def test_backfill_does_not_touch_another_cameras_results(conn):
    out = save_result(_payload(camera_id="thermal_1"), connection=conn)

    linked = backfill_frame_id(
        conn, camera_id="colour_1", ts="2026-09-01 14:17:28", frame_id=42
    )

    assert linked == 0
    row = conn.execute(
        "SELECT frame_id FROM results WHERE id = ?", (out["id"],)
    ).fetchone()
    assert row[0] is None


def test_a_payload_without_a_detection_list_is_rejected(conn):
    with pytest.raises(ValueError, match="detections"):
        save_result(_payload(detections="not a list"), connection=conn)

    assert conn.execute("SELECT COUNT(*) FROM results").fetchone()[0] == 0


def test_a_missing_frames_table_does_not_lose_the_result(conn):
    # The result matters more than the link; a schema gap must not drop it.
    conn.execute("DROP TABLE frames")

    out = save_result(_payload(), connection=conn)

    assert out["ok"] is True
    assert out["frame_id"] is None
