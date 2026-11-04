import pytest

from app.dependencies.database_actions.sqlite_database_actions import SqliteDatabaseActions


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
        "depth": 100.0,
    }
    headers = ["depth"]
    query, parameters = db._construct_search_query(terms, "sku_table", headers)

    assert query == "SELECT * FROM sku_table WHERE (depth) = (?);"
    assert parameters == (100.0,)


def test_construct_fuzzy_search_query_pairs_each_value_with_the_threshold(db):
    terms = {
        "command": "search_phrase",
        "database_name": "churchill_database",
        "destination": "sku_table",
        "depth": 100.0,
        "radius": 250
    }
    headers = ["depth", "radius"]
    query, parameters = db._construct_fuzzy_search_query(terms, "sku_table", 20,headers)

    # a single threshold is a percentage of each measured value
    assert "ABS(depth - ?) <= ? AND ABS(radius - ?) <= ?" in query
    # WHERE pairs each value with its tolerance; ORDER BY repeats them to rank nearest first
    assert parameters == (100.0, 20.0, 250, 50.0) * 2
    assert "ORDER BY ABS(depth - ?) / ? + ABS(radius - ?) / ?" in query


def test_construct_fuzzy_search_query_uses_each_columns_own_tolerance(db):
    terms = {"depth": 25.0, "perimeter": 700.0}
    tolerances = {"depth": {"absolute": 1.5}, "perimeter": {"percent": 2.5}}
    query, parameters = db._construct_fuzzy_search_query(terms, "sku_table", tolerances, ["depth", "perimeter"])

    assert parameters == (25.0, 1.5, 700.0, 17.5) * 2


def test_a_tolerance_must_be_absolute_or_percent(db):
    with pytest.raises(ValueError):
        db._construct_fuzzy_search_query({"depth": 25.0}, "sku_table", {"depth": {"inches": 1}}, ["depth"])


def test_map_from_database_keys_rows_by_index_then_column(db):
    rows = [(1, 100.0, 250.0), (2, 105.0, 260.0)]
    mapped = db._map_from_database(rows, ["id", "diameter", "area"])

    assert mapped == {
        0: {"id": 1, "diameter": 100.0, "area": 250.0},
        1: {"id": 2, "diameter": 105.0, "area": 260.0},
    }


def test_the_old_mm_unit_name_is_rejected(db):
    # "absolute" replaced "mm": the unit is the column's own, not always millimetres
    with pytest.raises(ValueError):
        db._construct_fuzzy_search_query({"depth": 25.0}, "sku_table", {"depth": {"mm": 1}}, ["depth"])
