import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "app"))

from dependencies.state_machine.search_state import SearchState  # noqa: E402


class _Database:
    def __init__(self):
        self.database_map = []
        self.seen = None

    def set_database_map(self, table):
        self.database_map = ["sku_id", "sku_name", "region", "Tmax_tolerance"]

    def search(self, table, message, headers, threshold):
        self.seen = (table, list(headers), threshold)
        return {0: {"sku_id": message["sku_id"], "region": "V2", "Tmax_tolerance": "[88, 93]"}}


class _Output:
    topic = "indonesia/database/database_1/search"


class _Machine:
    def __init__(self, database):
        self.headers = ["sku_id", "sku_name", "model_name", "service_name"]
        self.search_headers = ["sku_id"]
        self.tables = {
            "sku_tolerances": {
                "columns": ["sku_id", "region", "Tmax_tolerance"],
                "searchable_columns": ["sku_id"],
            }
        }
        self.database = {"indonesia": database}
        self.service_output = _Output()


class _Client:
    def __init__(self):
        self.published = []

    def publish(self, topic, payload):
        self.published.append((topic, payload))


def test_a_tolerances_search_publishes_the_tolerance_columns():
    database = _Database()
    machine = _Machine(database)
    state = SearchState(machine, {})
    client = _Client()

    state._fuzzy_search_database(
        client,
        {
            "database_name": "indonesia",
            "database_table": "sku_tolerances",
            "sku_id": "260_non_autolock",
        },
        machine.database,
        machine.search_headers,
        0,
    )

    assert database.seen == ("sku_tolerances", ["sku_id"], 0)
    assert machine.headers == ["sku_id", "region", "Tmax_tolerance"]
