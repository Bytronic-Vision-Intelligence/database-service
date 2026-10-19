from datetime import datetime

from app.dependencies.sqlite_database_actions import SqliteDatabaseActions
from app.main import _purge_old_rows

NOW = datetime(2026, 10, 19, 12, 0, 0)


def _results_db(tmp_path, stamps):
    actions = SqliteDatabaseActions(str(tmp_path / "seal.db"))
    actions.connection.execute(
        "CREATE TABLE seal_width_results (id INTEGER PRIMARY KEY AUTOINCREMENT, date_time TEXT, frame_verdict TEXT)"
    )
    actions.connection.executemany(
        "INSERT INTO seal_width_results (date_time, frame_verdict) VALUES (?, 'PASS')", [(s,) for s in stamps]
    )
    actions.connection.commit()
    return actions


def _stamps(actions):
    return [r[0] for r in actions.connection.execute("SELECT date_time FROM seal_width_results ORDER BY id")]


def test_rows_older_than_retention_days_are_deleted(tmp_path):
    actions = _results_db(tmp_path, [
        "2026-07-20 11:59:59.999",   # just over 90 days old
        "2026-07-21 12:00:00.500",   # just inside
        "2026-10-19 11:59:00.000",
    ])

    deleted = _purge_old_rows(actions, [{"table_name": "seal_width_results", "retention_days": 90}], now=NOW)

    assert deleted == 1
    assert _stamps(actions) == ["2026-07-21 12:00:00.500", "2026-10-19 11:59:00.000"]


def test_a_table_without_retention_days_is_left_alone(tmp_path):
    actions = _results_db(tmp_path, ["2020-01-01 00:00:00.000"])

    assert _purge_old_rows(actions, [{"table_name": "seal_width_results"}], now=NOW) == 0
    assert _purge_old_rows(actions, [{"table_name": "seal_width_results", "retention_days": 0}], now=NOW) == 0
    assert _stamps(actions) == ["2020-01-01 00:00:00.000"]


def test_rows_without_a_readable_stamp_are_never_deleted(tmp_path):
    actions = _results_db(tmp_path, ["", None, "20200101_000000", "old", "2020-01-01 00:00:00"])

    _purge_old_rows(actions, [{"table_name": "seal_width_results", "retention_days": 90}], now=NOW)

    assert _stamps(actions) == ["", None, "20200101_000000", "old"]


def test_bad_config_or_missing_table_does_not_raise(tmp_path):
    actions = _results_db(tmp_path, ["2020-01-01 00:00:00.000"])
    tables = [
        {"table_name": "missing_table", "retention_days": 90},
        {"table_name": "seal_width_results", "retention_days": "ninety"},
        {"table_name": "seal_width_results; DROP TABLE x", "retention_days": 90},
        {"table_name": "seal_width_results", "retention_days": 90, "retention_column": "no_such_column"},
    ]

    assert _purge_old_rows(actions, tables, now=NOW) == 0
    assert _stamps(actions) == ["2020-01-01 00:00:00.000"]
