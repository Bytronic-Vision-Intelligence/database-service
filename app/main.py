from dependencies.mqtt.mqtt_functions import *
from dependencies import loadConfig
from dependencies.database_actions.sqlite_database_actions import SqliteDatabaseActions

import time
from logging import info
from json import dumps
from mqtt_client import MQTTClient, MQTTConfig
#
MQTT_BROKERS = loadConfig.return_config_value("broker_details")
TOPICS = loadConfig.return_config_value("topics")
DATABASE_DETAILS = loadConfig.return_config_value("database")

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
    return db, headers, search_headers

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

def get_topic(topic_dict:dict, topic_name:str):
    '''returns the topic associated with the key value
    Args:
        topic_dict: a dictionary of topics, one value needs to be "name"
        topic_name: the name to search within the topic list
    Returns:
        the topic object accosiated with the name
    '''
    return next((t for t in topic_dict if t.get("name") == topic_name), None)

def main():
    config = loadConfig.get_config()
    broker_details = config.get('broker_details')
    service_id = config.get("service_id", "database_1")
    topics = loadConfig.return_config_value("topics")
    print(f"INFO : {service_id} starting \n\r")

    mqtt_config = MQTTConfig(host=MQTT_BROKERS["mqtt_ip"], port=MQTT_BROKERS["mqtt_port"])

    db, headers, search_headers = _setup_database(DATABASE_DETAILS)

    client = MQTTClient(mqtt_config)
    client.connect()

    topics = create_topic_listners(broker_details, topics)

    # these need to be made more generic, at some point a function needs to be made that will handle
    # taking info from the config and creating these
    colour_image = get_topic(topics,"colour_data")
    depth_image = get_topic(topics,"depth_data")
    depth_data = get_topic(topics,"request_command")
    ui_request = get_topic(topics,"hmi_request")

    try:
        while True:
            time.sleep(0.1)
            message = check_for_triggers(ui_request)
            instruction = message.get("database_instruction")
            if instruction != None: print(f"message = {instruction}")

            if instruction == "search_database":
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

            elif instruction == "write_database":
                write_data = message

                is_duplicate = db[
                    message.get("database_name")
                ].check_exists(
                    "sku",write_data["sku"],
                    message.get("database_table")
                )

                if is_duplicate: 
                    print(f"Error : Duplicate sku: {write_data['sku']} found")
                    continue

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

                try:
                    db[ message.get("database_name")].add_sku(
                        message.get("database_table"), 
                        write_data,
                        headers
                    )

                    print(f"Info : data added to database {write_data.get('database_name')}, {write_data.get('destination')}")
                except Exception as e:
                    info(f"Error transmitting data to database {e}")
                    print(f"Error transmitting data to database {e}")

            elif instruction == "remove_sku":
                is_found = db[
                    message.get("database_name")
                ].check_exists(
                    "sku",message.get("sku"),
                    message.get("database_table")
                )

                if not is_found: 
                    print(f"Error : sku: {message.get('sku')} not found")
                    continue

                try:
                    db[ message.get("database_name")].delete_sku(
                        message.get("database_table"), 
                        message.get("sku"),
                        "sku"
                    )

                    print(f"Info : data removed from database {write_data.get('database_name')}, {write_data.get('destination')}")
                except Exception as e:
                    info(f"Error deleting data in database {e}")
                    print(f"Error deleting data in database {e}")

            else:
                continue

    except KeyboardInterrupt:
        print(f"Info : {service_id} Shutting down subscribe listener and exiting.")

if __name__ == "__main__":
    main()