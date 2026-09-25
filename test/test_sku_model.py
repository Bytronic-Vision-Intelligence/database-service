import sqlite3

from app.dependencies.sqlite_database_actions import SqliteDatabaseActions
from app.main import build_sku_model_payload


def test_build_sku_model_payload_resolves_model_name_to_a_pt_file(tmp_path):
    payload = build_sku_model_payload(
        {
            "sku_id": "thermal_stirfry",
            "sku_name": "Stirfry",
            "model_name": "lws_thermal_stirfry_220926",
            "inference_service": 2,
        },
        str(tmp_path),
    )

    assert payload["sku_id"] == "thermal_stirfry"
    assert payload["model_name"] == "lws_thermal_stirfry_220926"
    assert payload["inference_service"] == 2
    assert payload["model_path"] == str((tmp_path / "lws_thermal_stirfry_220926.pt").resolve())


def test_sku_id_search_returns_the_model_name(tmp_path):
    database = tmp_path / "lws.db"
    connection = sqlite3.connect(database)
    connection.execute(
        "CREATE TABLE sku_table (sku_id TEXT, sku_name TEXT, model_name TEXT, inference_service INTEGER)"
    )
    connection.execute(
        "INSERT INTO sku_table VALUES (?, ?, ?, ?)",
        ("thermal_salad", "Salad", "lws_thermal_salad_220926", 2),
    )
    connection.commit()
    connection.close()

    actions = SqliteDatabaseActions(str(database))
    actions.set_database_map("sku_table")
    results = actions.search("sku_table", {"sku_id": "thermal_salad"}, ["sku_id"], 0)

    assert results[0]["model_name"] == "lws_thermal_salad_220926"
    assert results[0]["inference_service"] == 2
