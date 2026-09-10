"""Seed a fresh database from tracked SQL.

The .db file is gitignored - it is a live store the service writes to. This
module is what turns an empty file into a usable one, so a fresh checkout still
starts with a working sku_table.

Seeding only runs when sku_table is absent. An existing store is never
overwritten, so a restart cannot reset real data back to the sample rows.
"""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

#: Beside this module, deliberately. The release build bundles app/dependencies
#: (release-pipeline.yml: include-data-dirs), so the SQL travels with the code
#: that reads it and `__file__` resolves correctly inside the frozen binary.
#:
#: It used to live at <repo>/database/seed.sql, reached with parents[2]. Under
#: PyInstaller `__file__` sits inside the unpacked _MEIPASS directory, so that
#: became /tmp/database/seed.sql -- absent, so the seed silently did not run,
#: and the service then exited because sku_table was not there.
SEED_SQL_PATH = Path(__file__).resolve().parent / "seed.sql"


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
