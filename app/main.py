from dependencies.mqtt_functions import *

from dependencies import loadConfig
from dependencies.churchill_database_actions import ChurchillDatabaseActions

import time
from logging import info
from json import loads, dumps
from threading import Event
from queue import Queue
from mqtt_client import MQTTClient, MQTTConfig
#
MQTT_BROKERS = loadConfig.return_config_value("broker_details")
TOPICS = loadConfig.return_config_value("topics")
DATABASE_DETAILS = loadConfig.return_config_value("database")

def _wait_for_data(message:dict, queues:dict):
    '''Waits for data to be received from a dictionary of queue items, each queue item is then added to a dictionary this is a blocking function
    Args:
        message: a dictionary of data headings and data, this can be left unformatted if this is the first call
        queues: a dictionary of Queues to retreive data from
    Returns:
        data_json: a dictionary of data items with new information appended into them'''
    if message is None: raise ValueError("Error: Message cannot be empty")
    data_json = message
    queue_item = dict()
    for queue in queues:
        try:
            if not queue["is_subscribe"] or queue["is_trigger"]: continue
        except:
            continue
        try:
            queue_item =queue["queue"].get(timeout=1)
            queue_item = loads(queue_item)
        except Exception as e:
            queue_item["image"] = None
            info(f"Error: unable to get item from queue {e}")
            print(f"Error: unable to get item from queue {e}")

        data_json[f"{queue['name']}"] = queue_item["image"]

    return data_json

def _check_for_triggers(triggers:dict):
    '''Checks the queue for each of the trigger topics and returns the message when any of them have received one
    Args:
        triggers: a dictionary of topics
    Returns:
        message: the message received from the trigger as dictionary'''
    message = {"command": None}

    for trigger in triggers:
        try:
            if not trigger["is_trigger"]:continue
        except:
            continue

        try:
            message = loads(trigger["queue"].get_nowait())
        except Exception as e:
            if e != KeyError: info(f"error occured when checking for trigger {e}")
            continue

    return message

def _fuzzy_search_database(client:MQTTClient, message:dict, db:ChurchillDatabaseActions, threshold:float=0):
    '''performs a fuzzy search on the current database and publishes the results to a given MQTT broker
    Args:
        client: an MQTT client object
        message: a dict containing a search term
        db: a database actions object
    '''
    if client is None: raise ValueError("Error: client cannot be None")
    if message is None: raise ValueError("Error: message cannot be empty")
    if db is None: raise ValueError("Error: no database object detected")

    search_results = db[message["database_name"]].search(message["destination"], message, threshold)
    output_topic = next(
        topic["topic"]
        for topic in TOPICS
        if not topic["is_subscribe"]
    )
    json_results = dumps(search_results)
    client.publish(output_topic, json_results)
    print(search_results)

def main():
    config = MQTTConfig(host=MQTT_BROKERS["mqtt_ip"], port=MQTT_BROKERS["mqtt_port"])
    for database in DATABASE_DETAILS:
        db = {database["database_name"]: ChurchillDatabaseActions(
            database_location=database["file_location"]
        )}
        table_name = database["tables"][0]["churchill_sku_table"]
        if not db[database["database_name"]].check_table_exists(table_name):
            raise ConnectionError(f"Error : Could not connect to table {table_name}")
        db[database["database_name"]].set_database_map(table_name)
        db["threshold"]=database["search_threshold"]

    client = MQTTClient(config)
    client.connect()

    stop_event = Event()
    for topic in TOPICS:
        if not topic["is_subscribe"]:
            continue
        topic["queue"] = Queue()
        
        topic["thread"] = start_subscribe_thread(
            MQTT_BROKERS["mqtt_ip"], 
            MQTT_BROKERS["mqtt_port"], 
            topic["topic"], 
            topic["queue"],
            stop_event
        )

    try:
        while True:
            time.sleep(0.1)
            message = _check_for_triggers(TOPICS)
            if message["command"] == "search_phrase":
                try:
                    _fuzzy_search_database(client, message, db, db["threshold"])

                except Exception as e:
                    info(f"Error: fuzzy search fialed: {e}")
                    print(f"Error: fuzzy search fialed: {e}")
            elif message["command"] == "add_phrase":
                new_dictionary_data = _wait_for_data(message, TOPICS)
                try:
                    db[message["database_name"]].add_sku(message["destination"], new_dictionary_data)
                except Exception as e:
                    info(f"Error transmitting data to database {e}")
                    print(f"Error transmitting data to database {e}")
            else:
                continue

    except KeyboardInterrupt:
        print("Shutting down subscribe listener and exiting.")

if __name__ == "__main__":
    main()