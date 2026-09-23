import pytest

from app.dependencies.sqlite_database_actions import SqliteDatabaseActions


@pytest.fixture
def db():
    '''An in-memory database with a single sku_table, mirroring the shape
    described in config.yaml.'''
    actions = SqliteDatabaseActions(":memory:")
    actions.connection.execute(
        "CREATE TABLE sku_table (id INTEGER PRIMARY KEY, diameter REAL, area REAL)"
    )
    return actions


def test_check_table_exists_distinguishes_present_from_missing(db):
    # main() refuses to start when this returns False, so both branches matter
    assert db.check_table_exists("sku_table") is True
    assert db.check_table_exists("no_such_table") is False


def test_set_database_map_reads_column_names_in_order(db):
    # _map_from_database zips against this, so order is part of the contract
    db.set_database_map("sku_table")
    assert db.database_map == ["id", "diameter", "area"]


def test_construct_search_query_drops_control_keys_and_nulls(db):
    terms = {
        "command": "search_phrase",
        "database_name": "churchill_database",
        "destination": "sku_table",
        "diameter": 100.0,
        "area": None,
    }
    # The columns to match on are passed in rather than inferred from `terms`:
    # the message also carries control keys (command, destination) and the
    # caller -- not this method -- knows which columns are searchable.
    query, parameters = db._construct_search_query(terms, "sku_table", ["diameter"])

    assert query == "SELECT * FROM sku_table WHERE (diameter) = (?);"
    assert parameters == (100.0,)


def test_construct_fuzzy_search_query_pairs_each_value_with_the_threshold(db):
    terms = {
        "command": "search_phrase",
        "database_name": "churchill_database",
        "destination": "sku_table",
        "diameter": 100.0,
        "area": 250.0,
    }
    query, parameters = db._construct_fuzzy_search_query(
        terms, "sku_table", 20, ["diameter", "area"]
    )

    assert "ABS(diameter - ?) <= ? AND ABS(area - ?) <= ?" in query
    assert parameters == (100.0, 20, 250.0, 20)


def test_map_from_database_keys_rows_by_index_then_column(db):
    rows = [(1, 100.0, 250.0), (2, 105.0, 260.0)]
    mapped = db._map_from_database(rows, ["id", "diameter", "area"])

    assert mapped == {
        0: {"id": 1, "diameter": 100.0, "area": 250.0},
        1: {"id": 2, "diameter": 105.0, "area": 260.0},
    }


@pytest.fixture
def plates():
    '''A table shaped like churchill's test_table: measurements, images, name.'''
    actions = SqliteDatabaseActions(":memory:")
    actions.connection.execute(
        "CREATE TABLE test_table ("
        "Id TEXT PRIMARY KEY, depth_data TEXT, colour_data TEXT, "
        "depth REAL, perimeter REAL, radius REAL, sku TEXT)"
    )
    actions.connection.executemany(
        "INSERT INTO test_table VALUES (?, ?, ?, ?, ?, ?, ?)",
        [
            ("uuid-1", "d1", "c1", 31.0, 17724.0, 55.0, "TBD"),
            ("uuid-2", "d2", "c2", 32.0, 17730.0, 56.0, "TBD"),
        ],
    )
    actions.connection.commit()
    return actions


EDITABLE = ["sku"]


def test_construct_update_query_sets_only_the_named_column(plates):
    query, parameters = plates._construct_update_query(
        {"sku": "BRACKET-12"}, "test_table", "uuid-1", EDITABLE
    )

    assert query == "UPDATE test_table SET sku = ? WHERE id = ?;"
    # Row id last, so it lines up with the WHERE placeholder rather than the SET.
    assert parameters == ("BRACKET-12", "uuid-1")


def test_update_sku_changes_the_named_row_only(plates):
    changed = plates.update_sku("test_table", "uuid-1", {"sku": "BRACKET-12"}, EDITABLE)

    assert changed == 1
    rows = dict(
        plates.connection.execute("SELECT Id, sku FROM test_table").fetchall()
    )
    assert rows == {"uuid-1": "BRACKET-12", "uuid-2": "TBD"}


def test_update_sku_leaves_the_measurements_alone(plates):
    """A rename must not disturb what the capture measured."""
    before = plates.connection.execute(
        "SELECT depth, perimeter, radius, colour_data FROM test_table WHERE Id = ?",
        ("uuid-1",),
    ).fetchone()

    plates.update_sku("test_table", "uuid-1", {"sku": "BRACKET-12"}, EDITABLE)

    after = plates.connection.execute(
        "SELECT depth, perimeter, radius, colour_data FROM test_table WHERE Id = ?",
        ("uuid-1",),
    ).fetchone()
    assert before == after


def test_update_sku_reports_zero_when_no_row_carries_the_id(plates):
    """Distinguishable from success, so the operator is told rather than not."""
    assert plates.update_sku("test_table", "nope", {"sku": "X"}, EDITABLE) == 0


def test_update_refuses_a_column_config_did_not_permit(plates):
    # Measurements describe a capture that happened; typing over them would be
    # a fabrication, so the whitelist -- not the request -- decides.
    with pytest.raises(ValueError, match="not editable"):
        plates._construct_update_query(
            {"radius": 9.0}, "test_table", "uuid-1", EDITABLE
        )


def test_update_refuses_an_injected_column_name(plates):
    # Column names are interpolated, not bound, so this is the guard that matters.
    with pytest.raises(ValueError, match="Invalid database column name"):
        plates._construct_update_query(
            {"sku = 'x' --": "y"}, "test_table", "uuid-1", EDITABLE
        )


def test_update_refuses_an_injected_table_name(plates):
    with pytest.raises(ValueError, match="Invalid database table name"):
        plates._construct_update_query(
            {"sku": "y"}, "test_table; DROP TABLE test_table", "uuid-1", EDITABLE
        )


@pytest.mark.parametrize(
    "values, row_id, editable, expected",
    [
        ({}, "uuid-1", EDITABLE, "No data fields supplied"),
        ({"sku": "y"}, "", EDITABLE, "A row id is required"),
        ({"sku": "y"}, None, EDITABLE, "A row id is required"),
        ({"sku": "y"}, "uuid-1", [], "No editable columns configured"),
    ],
)
def test_update_refuses_incomplete_requests(plates, values, row_id, editable, expected):
    with pytest.raises(ValueError, match=expected):
        plates._construct_update_query(values, "test_table", row_id, editable)
