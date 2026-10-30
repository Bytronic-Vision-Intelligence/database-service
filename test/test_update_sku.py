import pytest

from app.dependencies.database_actions.sqlite_database_actions import SqliteDatabaseActions

HEADERS = ["id", "depth", "perimeter", "radius", "depth_data", "colour_data", "sku"]


@pytest.fixture
def db():
    '''An in-memory test_table shaped like the Churchill one, holding two parts.'''
    actions = SqliteDatabaseActions(":memory:")
    actions.connection.execute(
        "CREATE TABLE test_table (id TEXT, depth REAL, perimeter REAL, radius REAL, "
        "depth_data TEXT, colour_data TEXT, sku TEXT, description TEXT)")
    actions.connection.executemany(
        "INSERT INTO test_table VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        [("id-13", 20.44, 454.6, 95.9, "old depth", "old colour", "13", None),
         ("id-15", 24.08, 768.9, 126.5, "depth 15", "colour 15", "15", None)])
    actions.connection.commit()
    return actions


def row(db, sku):
    return db.connection.execute(
        "SELECT id, depth, perimeter, radius, depth_data, colour_data FROM test_table WHERE sku = ?", (sku,)).fetchone()


def test_re_capturing_a_part_replaces_its_stored_capture(db):
    capture = {"sku": "13", "depth": 26.09, "perimeter": 846.5, "radius": 136.3,
               "depth_data": "new depth", "colour_data": "new colour"}
    db.update_sku("test_table", capture, list(HEADERS))

    assert row(db, "13") == ("id-13", 26.09, 846.5, 136.3, "new depth", "new colour")


def test_updating_one_part_leaves_the_others_alone(db):
    db.update_sku("test_table", {"sku": "13", "depth": 26.09}, list(HEADERS))

    assert row(db, "15") == ("id-15", 24.08, 768.9, 126.5, "depth 15", "colour 15")


def test_columns_missing_from_the_capture_keep_their_stored_value(db):
    # a capture that timed out on one image must not overwrite it with the text "None"
    db.update_sku("test_table", {"sku": "13", "depth": 26.09}, list(HEADERS))

    assert row(db, "13") == ("id-13", 26.09, 454.6, 95.9, "old depth", "old colour")


def test_update_does_not_change_the_callers_column_list(db):
    # the state machine shares this list with every later insert and search
    headers = list(HEADERS)
    db.update_sku("test_table", {"sku": "13", "depth": 26.09}, headers)

    assert headers == HEADERS


def test_a_new_part_stores_its_description_and_leaves_missing_fields_empty(db):
    db.add_sku("test_table", {"sku": "20", "depth": 25.0, "description": "Blue rim bowl"},
               HEADERS + ["description"])
    stored = db.connection.execute(
        "SELECT id, description, colour_data FROM test_table WHERE sku = '20'").fetchone()

    assert stored[0] and stored[1] == "Blue rim bowl" and stored[2] is None


def test_a_search_returns_the_nearest_plates_first_and_no_more_than_asked(db):
    # three same-size plates stored far-to-near: row order would give the farthest first
    db.connection.executemany(
        "INSERT INTO test_table (id, depth, perimeter, radius, sku) VALUES (?, ?, ?, ?, ?)",
        [("a", 24.3, 718.0, 116.0, "far"), ("b", 24.36, 719.5, 116.2, "near"), ("c", 24.36, 719.9, 116.3, "nearest")])
    db.connection.commit()
    db.set_database_map("test_table")
    tolerances = {"depth": {"mm": 2}, "perimeter": {"percent": 2.5}, "radius": {"percent": 2.5}}
    found = db.search("test_table", {"depth": 24.36, "perimeter": 719.9, "radius": 116.3},
                      ["depth", "perimeter", "radius"], tolerances, 2)

    assert [row["sku"] for row in found.values()] == ["nearest", "near"]
