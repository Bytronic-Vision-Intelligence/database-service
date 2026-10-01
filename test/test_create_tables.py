import sqlite3
import sys
from pathlib import Path

import yaml

TOOLS = Path(__file__).resolve().parents[1] / "developer_tools"
sys.path.insert(0, str(TOOLS))

import create_tables


def _write_config(path: Path, database: Path) -> None:
    config = {
        "database-service": {
            "service": {
                "database": str(database),
                "tables": [
                    {
                        "table_name": "sku_models",
                        "columns": ["sku_id", "sku_name"],
                        "searchable_columns": ["sku_id"],
                    },
                    {
                        "table_name": "results_table",
                        "columns": ["process_id", {"overall_pass": "INTEGER"}],
                        "indexes": ["process_id"],
                    },
                ],
            }
        }
    }
    path.write_text(yaml.safe_dump(config), encoding="utf-8")


def test_create_tables_renames_capture_id_to_process_id(tmp_path):
    database = tmp_path / "lws.db"
    config_path = tmp_path / "config.yaml"
    _write_config(config_path, database)
    connection = sqlite3.connect(database)
    connection.execute(
        "CREATE TABLE results_table ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, capture_id TEXT, overall_pass INTEGER)"
    )
    connection.execute(
        "CREATE INDEX idx_results_table_capture_id ON results_table (capture_id)"
    )
    connection.execute(
        "CREATE TABLE sku_models (id INTEGER PRIMARY KEY AUTOINCREMENT, sku_id TEXT, sku_name TEXT)"
    )
    connection.commit()
    connection.close()

    report = create_tables.create_tables(config_path, service_root=tmp_path)

    assert report[2].startswith("updated results_table")
    connection = sqlite3.connect(database)
    columns = {
        row[1] for row in connection.execute("PRAGMA table_info(results_table)")
    }
    connection.close()
    assert "process_id" in columns
    assert "capture_id" not in columns


def test_create_tables_creates_then_leaves_an_existing_database(tmp_path):
    database = tmp_path / "lws.db"
    config_path = tmp_path / "config.yaml"
    _write_config(config_path, database)

    first = create_tables.create_tables(config_path, service_root=tmp_path)
    second = create_tables.create_tables(config_path, service_root=tmp_path)

    assert first[1:] == ["created sku_models", "created results_table"]
    assert second[1:] == ["unchanged sku_models", "unchanged results_table"]

    connection = sqlite3.connect(database)
    results = {
        row[1]: row[2]
        for row in connection.execute("PRAGMA table_info(results_table)")
    }
    assert results["process_id"] == "TEXT"
    assert results["overall_pass"] == "INTEGER"
    assert "process_id" in create_tables.indexed_columns(connection, "results_table")
    connection.close()


def test_create_tables_adds_a_missing_column(tmp_path):
    database = tmp_path / "lws.db"
    config_path = tmp_path / "config.yaml"
    _write_config(config_path, database)
    create_tables.create_tables(config_path, service_root=tmp_path)

    loaded = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    loaded["database-service"]["service"]["tables"][1]["columns"].append("note")
    config_path.write_text(yaml.safe_dump(loaded), encoding="utf-8")

    report = create_tables.create_tables(config_path, service_root=tmp_path)
    assert report[2] == "updated results_table: note"

    connection = sqlite3.connect(database)
    results = {
        row[1]: row[2]
        for row in connection.execute("PRAGMA table_info(results_table)")
    }
    connection.close()
    assert results["note"] == "TEXT"
