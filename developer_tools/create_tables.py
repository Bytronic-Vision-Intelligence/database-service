"""Create the SQLite tables listed under ``service.tables``.

Run this before starting the service, from the database-service directory:

    python developer_tools/create_tables.py --config ../configs/config.yaml

``--config`` may be the orchestrator file (a ``database-service`` section)
or a service config (``service.tables`` at the top). A bare column name is
TEXT. ``name: INTEGER`` or ``name: REAL`` sets the type. An existing table
is left in place; columns listed in config and missing from the table are
added.
"""

from __future__ import annotations

import argparse
import re
import sqlite3
from pathlib import Path

import yaml

from table_columns import parse_columns

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT.parent / "configs" / "config.yaml"


def service_section(config: dict) -> dict:
    """The database service mapping, whether the file is wrapped or not."""
    wrapped = config.get("database-service")
    if isinstance(wrapped, dict):
        config = wrapped
    service = config.get("service")
    if not isinstance(service, dict):
        raise SystemExit("Config has no database service section")
    if not service.get("database"):
        raise SystemExit("service.database is missing")
    if not service.get("tables"):
        raise SystemExit("service.tables is missing")
    return service


def database_path(service: dict, service_root: Path = ROOT) -> Path:
    """Resolve ``service.database`` from the database-service directory."""
    path = Path(str(service["database"]))
    if not path.is_absolute():
        path = service_root / path
    return path.resolve()


def _check_identifier(name: str) -> None:
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", str(name)):
        raise ValueError(f"Invalid database name: {name}")


def index_name(table_name: str, column: str) -> str:
    return f"idx_{table_name}_{column}"


def table_exists(connection: sqlite3.Connection, table_name: str) -> bool:
    row = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone()
    return row is not None


def indexed_columns(connection: sqlite3.Connection, table_name: str) -> set[str]:
    """Column names that already have an index on this table."""
    covered = set()
    rows = connection.execute(f"PRAGMA index_list({table_name})").fetchall()
    for row in rows:
        info = connection.execute(f"PRAGMA index_info({row[1]})").fetchall()
        for item in info:
            covered.add(item[2])
    return covered


def apply_table(connection: sqlite3.Connection, table: dict) -> str:
    """Create one configured table, or add columns it does not have yet."""
    table_name = str(table.get("table_name") or "").strip()
    if not table_name:
        raise SystemExit("A table entry is missing table_name")
    _check_identifier(table_name)
    columns = parse_columns(table.get("columns"))
    indexes = [str(name).strip() for name in (table.get("indexes") or []) if str(name).strip()]

    if not table_exists(connection, table_name):
        parts = ["id INTEGER PRIMARY KEY AUTOINCREMENT"]
        for name, column_type in columns:
            _check_identifier(name)
            parts.append(f"{name} {column_type}")
        connection.execute(f"CREATE TABLE {table_name} ({', '.join(parts)})")
        for column in indexes:
            _check_identifier(column)
            connection.execute(
                f"CREATE INDEX {index_name(table_name, column)} ON {table_name} ({column})"
            )
        connection.commit()
        return f"created {table_name}"

    existing = {
        row[1]
        for row in connection.execute(f"PRAGMA table_info({table_name})").fetchall()
    }
    added = []
    wanted = {name for name, _ in columns}
    if "process_id" in wanted and "capture_id" in existing and "process_id" not in existing:
        connection.execute(
            f"ALTER TABLE {table_name} RENAME COLUMN capture_id TO process_id"
        )
        existing.discard("capture_id")
        existing.add("process_id")
        added.append("process_id")
    for name, column_type in columns:
        if name in existing:
            continue
        _check_identifier(name)
        connection.execute(f"ALTER TABLE {table_name} ADD COLUMN {name} {column_type}")
        added.append(name)
    covered = indexed_columns(connection, table_name)
    for column in indexes:
        if column in covered:
            continue
        _check_identifier(column)
        connection.execute(
            f"CREATE INDEX IF NOT EXISTS {index_name(table_name, column)} "
            f"ON {table_name} ({column})"
        )
        added.append(f"index {column}")
    connection.commit()
    if not added:
        return f"unchanged {table_name}"
    return f"updated {table_name}: {', '.join(added)}"


def create_tables(config_path: Path, service_root: Path = ROOT) -> list[str]:
    """Apply every table in the config. Returns one status line per table."""
    with config_path.open(encoding="utf-8") as handle:
        loaded = yaml.safe_load(handle)
    if not isinstance(loaded, dict):
        raise SystemExit(f"Config root must be a mapping: {config_path}")
    service = service_section(loaded)
    path = database_path(service, service_root)
    if not path.parent.is_dir():
        raise SystemExit(f"Database directory does not exist: {path.parent}")
    connection = sqlite3.connect(path)
    report = [str(path)]
    try:
        for table in service["tables"]:
            report.append(apply_table(connection, table))
    finally:
        connection.close()
    return report


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description="Create configured SQLite tables.")
    parser.add_argument(
        "--config",
        default=str(DEFAULT_CONFIG),
        help="Orchestrator config or database-service config (default: ../configs/config.yaml)",
    )
    args = parser.parse_args(argv)
    config_path = Path(args.config)
    if not config_path.is_file():
        raise SystemExit(f"Config not found: {config_path}")
    for line in create_tables(config_path):
        print(line)


if __name__ == "__main__":
    main()
