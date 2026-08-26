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
    query, parameters = db._construct_search_query(terms, "sku_table")

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
    query, parameters = db._construct_fuzzy_search_query(terms, "sku_table", 20)

    assert "ABS(diameter - ?) <= ? AND ABS(area - ?) <= ?" in query
    assert parameters == (100.0, 20, 250.0, 20)


def test_map_from_database_keys_rows_by_index_then_column(db):
    rows = [(1, 100.0, 250.0), (2, 105.0, 260.0)]
    mapped = db._map_from_database(rows, ["id", "diameter", "area"])

    assert mapped == {
        0: {"id": 1, "diameter": 100.0, "area": 250.0},
        1: {"id": 2, "diameter": 105.0, "area": 260.0},
    }
