"""Read a ``tables`` entry's column list.

A column is a name, stored as TEXT::

    - sku_id

or a one-key map when the type is not text::

    - overall_pass: INTEGER
    - colour_verdict_confidence: REAL
"""

from __future__ import annotations

COLUMN_TYPES = {"TEXT", "INTEGER", "REAL"}


def parse_columns(columns) -> list[tuple[str, str]]:
    """Return ``(name, type)`` for each configured column."""
    if not isinstance(columns, list) or not columns:
        raise ValueError("columns must be a non-empty list")
    parsed = []
    for column in columns:
        name, column_type = _column(column)
        if column_type not in COLUMN_TYPES:
            raise ValueError(f"Invalid column type for {name}: {column_type}")
        parsed.append((name, column_type))
    return parsed


def _column(column) -> tuple[str, str]:
    if isinstance(column, str) and column.strip():
        return column.strip(), "TEXT"
    if isinstance(column, dict) and len(column) == 1:
        name, column_type = next(iter(column.items()))
        name = str(name).strip()
        column_type = str(column_type).strip().upper()
        if name and column_type:
            return name, column_type
    raise ValueError(f"Invalid column entry: {column!r}")
