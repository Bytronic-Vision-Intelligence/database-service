"""Seed a fresh database from tracked SQL.

The .db file is gitignored - it is a live store the service writes to. This
module is what turns an empty file into a usable one, so a fresh checkout still
starts with a working sku_table.

Seeding only runs when sku_table is absent. An existing store is never
overwritten, so a restart cannot reset real data back to the sample rows.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

def _seed_sql_path() -> Path:
    """Where the seed SQL is, in a checkout and inside a frozen binary.

    The two differ. PyInstaller is given `--paths app`, so the package is
    imported as `dependencies` and __file__ sits at <_MEIPASS>/dependencies/.
    The data is added as `./app/dependencies:./app/dependencies`, so the SQL
    lands at <_MEIPASS>/app/dependencies/ -- next to the package's source
    layout, not next to the package.

    Both are checked rather than guessed. Mapping the data to ./dependencies
    instead would remove the second case, but build-binary.sh and
    release-pipeline.yml are identical across six repositories and that is a
    change to make in service-template, not here.
    """
    beside_the_module = Path(__file__).resolve().parent / "seed.sql"
    if beside_the_module.is_file():
        return beside_the_module

    bundle = getattr(sys, "_MEIPASS", None)
    if bundle:
        return Path(bundle) / "app" / "dependencies" / "seed.sql"
    return beside_the_module


SEED_SQL_PATH = _seed_sql_path()


def _has_table(connection, table: str) -> bool:
    row = connection.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone()
    return row is not None


def seed_database(connection, *, table: str = "sku_table") -> bool:
    """Apply the seed SQL when `table` is missing.

    Args:
        connection: an open sqlite3 connection.
        table: the table whose absence means "this database is fresh".
    Returns:
        True when the seed was applied, False when the store already existed.
    """
    if _has_table(connection, table):
        return False

    if not SEED_SQL_PATH.is_file():
        logger.warning("Seed SQL not found at %s; starting empty", SEED_SQL_PATH)
        return False

    connection.executescript(SEED_SQL_PATH.read_text(encoding="utf-8"))
    connection.commit()
    logger.info("Seeded %s from %s", table, SEED_SQL_PATH)
    return True
