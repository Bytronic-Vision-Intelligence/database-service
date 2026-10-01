from app.dependencies.sqlite_database_actions import SqliteDatabaseActions
from app.main import _write_entry


def test_a_write_message_inserts_its_column_fields(tmp_path):
    database = tmp_path / "lws.db"
    actions = SqliteDatabaseActions(str(database))
    actions.connection.execute(
        "CREATE TABLE results_table ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, "
        "process_id TEXT, overall_verdict TEXT, note TEXT)"
    )
    actions.connection.commit()
    tables = [{
        "table_name": "results_table",
        "columns": ["process_id", "overall_verdict", "note"],
    }]

    _write_entry(actions, tables, {
        "table": "results_table",
        "process_id": "abc",
        "overall_verdict": "fail",
        "note": "seal check",
    })

    stored = actions.connection.execute(
        "SELECT process_id, overall_verdict, note FROM results_table"
    ).fetchall()
    assert stored == [("abc", "fail", "seal check")]


def test_an_unknown_table_is_not_inserted(tmp_path):
    database = tmp_path / "lws.db"
    actions = SqliteDatabaseActions(str(database))
    actions.connection.execute(
        "CREATE TABLE results_table (id INTEGER PRIMARY KEY AUTOINCREMENT, process_id TEXT)"
    )
    actions.connection.commit()

    _write_entry(actions, [{"table_name": "results_table", "columns": ["process_id"]}], {
        "table": "other_table",
        "process_id": "abc",
    })

    count = actions.connection.execute("SELECT COUNT(*) FROM results_table").fetchone()[0]
    assert count == 0
