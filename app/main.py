from dependencies.mqtt_functions import *

from dependencies import loadConfig, logging_setup
from dependencies.sqlite_database_actions import SqliteDatabaseActions

import time
from pathlib import Path
from logging import info
from json import dumps
from mqtt_client import MQTTClient, MQTTConfig


def require(config: dict, key: str):
    """Return a required top-level config value, or exit describing what is missing.

    Args:
        config: the loaded configuration mapping.
        key: the top-level key the service cannot start without.
    Returns:
        the value stored under `key`.
    Raises:
        SystemExit: when `key` is absent, naming both the key and the file.
    """
    if key not in config or config[key] is None:
        try:
            where = f" in {loadConfig.config_path()}"
        except SystemExit:
            where = ""
        raise SystemExit(f"Missing required config key '{key}'{where}")
    return config[key]


def _setup_database(service: dict):
    '''used to setup a database from the `service` config section'''
    database_path = service["database"]
    database_name = Path(database_path).stem
    db = {database_name: SqliteDatabaseActions(
        database_location=database_path
    )}
    table = service["tables"][0]
    table_name = table["table_name"]
    headers = table["columns"]
    search_headers = table["searchable_columns"]
    info("table headers: %s", headers)
    if not db[database_name].check_table_exists(table_name):
        raise ConnectionError(f"Error : Could not connect to table {table_name}")
    db[database_name].set_database_map(table_name)
    db["threshold"] = service["search_threshold"]
    db["database_name"] = database_name
    db["table_name"] = table_name
    return db, search_headers, headers

def build_sku_model_payload(row: dict, models_directory: str | None) -> dict:
    """Shape a sku_table row into the message inference uses to load weights."""
    payload = {
        "sku_id": row.get("sku_id"),
        "sku_name": row.get("sku_name"),
        "model_name": row.get("model_name"),
    }
    if row.get("inference_service") not in (None, ""):
        payload["inference_service"] = row.get("inference_service")
    model_name = str(row.get("model_name") or "").strip()
    if model_name and models_directory:
        filename = model_name if model_name.endswith(".pt") else f"{model_name}.pt"
        payload["model_path"] = str((Path(models_directory) / filename).resolve())
    return payload


def _publish_sku_model(client, sku_id: str, db: dict, topics: list, models_directory):
    """Look up one SKU and publish its model on `database_output`.

    The message is retained so an inference service that is still loading its
    startup weights still receives the selection.
    """
    database_name = db["database_name"]
    table_name = db["table_name"]
    results = db[database_name].search(table_name, {"sku_id": sku_id}, ["sku_id"], 0)
    rows = list(results.values()) if isinstance(results, dict) else []
    if not rows or not isinstance(rows[0], dict):
        info("No sku_table row for sku_id %s", sku_id)
        return

    payload = build_sku_model_payload(rows[0], models_directory)
    output_topic = next(
        topic["topic"]
        for topic in topics
        if topic.get("name") == "database_output"
    )
    client.publish(output_topic, payload, retain=True)
    info("Published model for sku %s: %s", sku_id, payload.get("model_path") or payload.get("model_name"))


def _fuzzy_search_database(
        client:MQTTClient,
        message:dict,
        db:SqliteDatabaseActions,
        headers,
        topics: list,
        threshold:float=0
    ):
    '''performs a fuzzy search on the current database and publishes the results to a given MQTT broker
    Args:
        client: an MQTT client object
        message: a dict containing a search term
        db: a database actions object
        topics: configured MQTT topic entries
    '''
    if client is None: raise ValueError("Error: client cannot be None")
    if message is None: raise ValueError("Error: message cannot be empty")
    if db is None: raise ValueError("Error: no database object detected")

    response = dict()

    database_name = message.get("database_name")
    if database_name == None: raise ValueError(f"Error : database name cannot be None")
    table_name = message.get("database_table")
    if table_name == None: raise ValueError(f"Error : table name cannot be None")

    search_results = db[database_name].search(table_name, message,headers, threshold)
    output_topic = next(
        topic["topic"]
        for topic in topics
        if topic.get("name") == "database_output"
    )

    response["matches_found"]=len(search_results)
    client.publish(f"{output_topic}", dumps(response))

    if len(search_results) == 0:return

    packet_list = packetize_results(search_results)
    client.publish_many(packet_list)

def main(argv=None):
    args = loadConfig.parse_cli(argv)

    config = loadConfig.get_config(args.config)

    log_settings = config.get("logging") or {}
    logging_setup.configure(log_settings.get("level", logging_setup.DEFAULT_LEVEL))

    mqtt = require(config, "mqtt")
    service = require(config, "service")
    topics = require(mqtt, "topics")
    service_id = config.get("service_id", "database_1")
    info("%s starting", service_id)

    mqtt_config = MQTTConfig(host=mqtt["mqtt_ip"], port=mqtt["mqtt_port"])

    db, search_headers, headers = _setup_database(service)

    client = MQTTClient(mqtt_config)
    client.connect()

    topics = create_topic_listners(mqtt, topics)

    # these need to be made more generic, at some point a function needs to be made that will handle
    # taking info from the config and creating these
    colour_image = next((t for t in topics if t.get("name") == "colour_data"), None)
    depth_image = next((t for t in topics if t.get("name") == "depth_data"), None)
    depth_data = next((t for t in topics if t.get("name") == "request_command"), None)
    ui_request = next((t for t in topics if t.get("name") == "ui_instruction"), None)

    try:
        while True:
            time.sleep(0.1)
            message = check_trigger(ui_request)
            if not message:
                continue
            sku_id = message.get("sku_id") or message.get("sku")
            if message.get("database_instruction") == "search_database":
                try:
                    colour_image_out = check_trigger(colour_image, True)
                    depth_image_out = check_trigger(depth_image, True)
                    depth_data_out = check_trigger(depth_data, True)
                    search_data = {
                        **message,
                        **colour_image_out,
                        **depth_image_out,
                        **depth_data_out
                    }

                    _fuzzy_search_database(
                        client,
                        search_data,
                        db,
                        search_headers,
                        topics,
                        db["threshold"]
                    )

                except Exception as e:
                    info("Error: %s fuzzy search failed: %s", service_id, e)

            elif message.get("database_instruction") == "write_database":
                write_data = message

                colour_image_out = check_trigger(colour_image, True)
                colour_image_out["colour_data"] = colour_image_out.pop("image")

                depth_image_out = check_trigger(depth_image, True)
                depth_image_out["depth_data"] = depth_image_out.pop("image")
                depth_data_out = check_trigger(depth_data, True)

                write_data = {
                    **write_data,
                    **colour_image_out,
                    **depth_image_out,
                    **depth_data_out
                }
                write_data["sku"] = "TBD"
                try:
                    db[write_data["database_name"]].add_sku(
                        write_data["database_table"],
                        write_data,
                        headers
                    )

                    info(
                        "data added to database %s, %s",
                        write_data.get("database_name"),
                        write_data.get("destination"),
                    )
                except Exception as e:
                    info("Error transmitting data to database %s", e)
            elif sku_id:
                try:
                    _publish_sku_model(
                        client,
                        str(sku_id).strip(),
                        db,
                        topics,
                        service.get("models_directory"),
                    )
                except Exception as e:
                    info("Error: %s sku model lookup failed: %s", service_id, e)
            else:
                continue

    except KeyboardInterrupt:
        info("%s shutting down subscribe listener and exiting.", service_id)

if __name__ == "__main__":
    main()
