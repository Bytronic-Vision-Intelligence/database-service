from dependencies.mqtt_functions import *

from dependencies import loadConfig
from dependencies.sqlite_database_actions import SqliteDatabaseActions

import time
from logging import info
from json import loads, dumps
from threading import Event
from queue import Queue
from mqtt_client import MQTTClient, MQTTConfig
from sys import getsizeof
#
MQTT_BROKERS = loadConfig.return_config_value("broker_details")
TOPICS = loadConfig.return_config_value("topics")
DATABASE_DETAILS = loadConfig.return_config_value("database")
global service_id

def _setup_database(database:dict):
    '''used to setup a database'''
    db = {database["database_name"]: SqliteDatabaseActions(
        database_location=database["file_location"]
    )}
    table_name = database["tables"][0]["database_table"]
    headers = database["tables"][0]["columns"]
    search_headers = database["tables"][0]["searchable_columns"]
    print(headers)
    if not db[database["database_name"]].check_table_exists(table_name):
        raise ConnectionError(f"Error : Could not connect to table {table_name}")
    db[database["database_name"]].set_database_map(table_name)
    db["threshold"]=database["search_threshold"]
    return db, search_headers

def _fuzzy_search_database(
        client:MQTTClient, 
        message:dict, 
        db:SqliteDatabaseActions,
        headers,
        threshold:float=0
    ):
    '''performs a fuzzy search on the current database and publishes the results to a given MQTT broker
    Args:
        client: an MQTT client object
        message: a dict containing a search term
        db: a database actions object
    '''
    if client is None: raise ValueError("Error: client cannot be None")
    if message is None: raise ValueError("Error: message cannot be empty")
    if db is None: raise ValueError("Error: no database object detected")

    result_packet = dict()
    response = dict()

    database_name = message.get("database_name")
    if database_name == None: raise ValueError(f"Error : database name cannot be None")
    table_name = message.get("database_table")
    if table_name == None: raise ValueError(f"Error : table name cannot be None")

    search_results = db[database_name].search(table_name, message,headers, threshold)
    output_topic = next(
        topic["topic"]
        for topic in TOPICS
        if topic.get("name") == "database_output"
    )
    
    response["matches_found"]=len(search_results)
    client.publish(f"{output_topic}", dumps(response))
    
    if len(search_results) == 0:return

    packet_list = packetize_results(search_results)
    client.publish_many(packet_list)

def main():
    config = loadConfig.get_config()
    broker_details = config.get('broker_details')
    service_id = config.get("service_id", "database_1")
    topics = loadConfig.return_config_value("topics")
    print(f"INFO : {service_id} starting \n\r")

    mqtt_config = MQTTConfig(host=MQTT_BROKERS["mqtt_ip"], port=MQTT_BROKERS["mqtt_port"])

    db_list = []
    for database in DATABASE_DETAILS:
        db, search_headers = _setup_database(database)
        db_list.append([db, search_headers])

    client = MQTTClient(mqtt_config)
    client.connect()

    topics = create_topic_listners(broker_details, topics)

    # these need to be made more generic, at some point a function needs to be made that will handle
    # taking info from the config and creating these
    colour_image = next((t for t in topics if t.get("name") == "colour_data"), None)
    depth_image = next((t for t in topics if t.get("name") == "depth_data"), None)
    depth_data = next((t for t in topics if t.get("name") == "request_command"), None)
    ui_request = next((t for t in topics if t.get("name") == "hmi_request"), None)

    try:
        while True:
            time.sleep(0.1)
            message = check_for_triggers(ui_request)
            if message.get("database_instruction") == "search_database":
                try:
                    colour_image_out = check_for_triggers(colour_image, True)
                    depth_image_out = check_for_triggers(depth_image, True)
                    depth_data_out = check_for_triggers(depth_data, True)
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
                        db["threshold"]
                    )

                except Exception as e:
                    info(f"Error: {service_id} fuzzy search failed: {e}")
                    print(f"Error: {service_id} fuzzy search failed: {e}")

            elif message.get("database_instruction") == "write_database":
                write_data = message

                colour_image_out = check_for_triggers(colour_image, True)
                colour_image_out["colour_data"] = colour_image_out.pop("image")

                depth_image_out = check_for_triggers(depth_image, True)
                depth_image_out["depth_data"] = depth_image_out.pop("image")
                depth_data_out = check_for_triggers(depth_data, True)

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

                    print(f"Info : data added to database {write_data.get('database_name')}, {write_data.get('destination')}")
                except Exception as e:
                    info(f"Error transmitting data to database {e}")
                    print(f"Error transmitting data to database {e}")
            else:
                continue

    except KeyboardInterrupt:
        print(f"Info : {service_id} Shutting down subscribe listener and exiting.")

if __name__ == "__main__":
    main()