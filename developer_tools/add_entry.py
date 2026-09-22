"""Insert one row from entry.json into a SQLite database.

Edit developer_tools/entry.json, then run:

    python developer_tools/add_entry.py

entry.json template:

    {
        "database": "path/to/database.db",
        "table": "table_name",
        "heading_1": "entry",
        "heading_2": "entry"
    }

`database` and `table` select the target. Every other key is inserted as a column.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))

from dependencies.sqlite_database_actions import SqliteDatabaseActions

ENTRY_PATH = Path(__file__).resolve().parent / "entry.json"
CONTROL_KEYS = {"database", "table"}


def main() -> None:
    with ENTRY_PATH.open("r", encoding="utf-8") as handle:
        entry = json.load(handle)

    db_path = Path(entry["database"])
    table = entry["table"]
    row = {
        key: value
        for key, value in entry.items()
        if key not in CONTROL_KEYS and value is not None
    }

    db = SqliteDatabaseActions(str(db_path))
    if not db.check_table_exists(table):
        raise ConnectionError(f"Could not find table '{table}' in {db_path}")

    db.add_sku(table, row, list(row.keys()))
    print(f"Added {row} to {table}")


if __name__ == "__main__":
    main()
