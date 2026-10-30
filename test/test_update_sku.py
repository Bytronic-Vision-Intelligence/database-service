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
