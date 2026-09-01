"""Seeding the sku_table.

The database file is no longer tracked in git - it is a live store that the
service writes to, and committing it meant every test run showed as a diff, and
reverting it pulled the frames/results tables out from under a running service.
The schema and its starting rows are seeded from SQL instead.
"""

import sqlite3

import pytest

from dependencies.seed import SEED_SQL_PATH, seed_database


@pytest.fixture
def conn():
    connection = sqlite3.connect(":memory:")
    yield connection
    connection.close()


def test_the_seed_file_ships_with_the_service():
    assert SEED_SQL_PATH.is_file(), f"seed SQL missing at {SEED_SQL_PATH}"


def test_seeding_creates_the_sku_table(conn):
    seed_database(conn)

    names = [
        r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    ]
    assert "sku_table" in names


def test_the_seeded_columns_match_what_the_service_expects(conn):
    # main() calls set_database_map(table), and the fuzzy search builds its
    # query from these column names.
    seed_database(conn)

    cols = [r[1] for r in conn.execute("PRAGMA table_info(sku_table)").fetchall()]
    assert cols == ["Id", "depth_data", "colour_data", "depth", "area", "perimeter"]


def test_the_starting_rows_are_present(conn):
    seed_database(conn)

    rows = conn.execute(
        "SELECT depth, area, perimeter FROM sku_table ORDER BY rowid"
    ).fetchall()
    assert rows == [
        (10.0, 299.0, 500.0),
        (10.0, 299.0, 500.0),
        (10.0, 259.0, 500.0),
        (150.0, 29.0, 50.0),
        (50.0, 2119.0, 20.0),
    ]


def test_seeding_is_idempotent(conn):
    seed_database(conn)
    seed_database(conn)

    assert conn.execute("SELECT COUNT(*) FROM sku_table").fetchone()[0] == 5


def test_seeding_never_touches_an_existing_table(conn):
    # A populated store must not be reset to the sample rows on restart.
    seed_database(conn)
    conn.execute("DELETE FROM sku_table")
    conn.execute(
        "INSERT INTO sku_table (depth, area, perimeter) VALUES (?, ?, ?)",
        (1.0, 2.0, 3.0),
    )
    conn.commit()

    seed_database(conn)

    rows = conn.execute("SELECT depth, area, perimeter FROM sku_table").fetchall()
    assert rows == [(1.0, 2.0, 3.0)], "seeding overwrote live data"
