"""Frame storage: JPEG to disk, metadata to SQLite.

Uses an in-memory database and tmp_path, so nothing here touches the real
churchill_database.db or the image store.
"""

import base64
import sqlite3

import pytest

from dependencies.frame_store import ensure_table, save_frame

# Minimal but structurally valid JPEG: SOI ... EOI
JPEG = b"\xff\xd8\xff\xe0" + b"body" + b"\xff\xd9"


@pytest.fixture
def conn():
    connection = sqlite3.connect(":memory:")
    ensure_table(connection)
    yield connection
    connection.close()


def _payload(**overrides):
    payload = {
        "command": "save_frame",
        "camera_id": "colour_1",
        "image": base64.b64encode(JPEG).decode("ascii"),
        "date_time": "2026-09-01 13:47:59",
    }
    payload.update(overrides)
    return payload


def test_ensure_table_is_idempotent(conn):
    # main() calls this on every boot; a second call must not fail or duplicate.
    ensure_table(conn)
    ensure_table(conn)

    names = [
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    ]
    assert names.count("frames") == 1


def test_save_frame_writes_the_file_and_inserts_a_row(conn, tmp_path):
    result = save_frame(_payload(), image_store=tmp_path, connection=conn)

    assert result["ok"] is True

    written = tmp_path / result["path"]
    assert written.is_file()
    assert written.read_bytes() == JPEG

    row = conn.execute(
        "SELECT camera_id, path, bytes FROM frames WHERE id = ?", (result["id"],)
    ).fetchone()
    assert row == ("colour_1", result["path"], len(JPEG))


def test_saved_path_is_relative_so_the_store_can_be_relocated(conn, tmp_path):
    result = save_frame(_payload(), image_store=tmp_path, connection=conn)

    assert not result["path"].startswith("/")
    assert str(tmp_path) not in result["path"]


def test_frames_are_foldered_by_day(conn, tmp_path):
    result = save_frame(_payload(date_time="2026-09-01 13:47:59"),
                        image_store=tmp_path, connection=conn)

    assert result["path"].startswith("20260901/")


def test_two_frames_in_the_same_second_do_not_overwrite_each_other(conn, tmp_path):
    first = save_frame(_payload(), image_store=tmp_path, connection=conn)
    second = save_frame(_payload(), image_store=tmp_path, connection=conn)

    assert first["path"] != second["path"]
    assert len(list(tmp_path.rglob("*.jpg"))) == 2


def test_save_frame_rejects_a_payload_that_is_not_base64(conn, tmp_path):
    with pytest.raises(ValueError, match="base64"):
        save_frame(_payload(image="not base64 !!!"), image_store=tmp_path, connection=conn)

    assert conn.execute("SELECT COUNT(*) FROM frames").fetchone()[0] == 0
    assert list(tmp_path.rglob("*.jpg")) == []


def test_save_frame_rejects_bytes_that_are_not_jpeg(conn, tmp_path):
    # A caller could base64 anything; only JPEG belongs in the image store.
    encoded = base64.b64encode(b"not a jpeg at all").decode("ascii")

    with pytest.raises(ValueError, match="JPEG"):
        save_frame(_payload(image=encoded), image_store=tmp_path, connection=conn)

    assert list(tmp_path.rglob("*.jpg")) == []


def test_insert_failure_removes_the_orphan_file(conn, tmp_path):
    # The file is written before the row, so a failed insert must clean up or
    # the store fills with images nothing points at.
    conn.execute("DROP TABLE frames")

    with pytest.raises(sqlite3.Error):
        save_frame(_payload(), image_store=tmp_path, connection=conn)

    assert list(tmp_path.rglob("*.jpg")) == [], "orphan file left behind"
