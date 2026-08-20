from dependencies.mqtt_functions import *

from dependencies import loadConfig
from dependencies.churchill_database_actions import ChurchillDatabaseActions

import time
from base64 import b64encode
from json import loads, dumps
import threading
from queue import Empty, Queue
from mqtt_client import MQTTClient, MQTTConfig
#
IP = loadConfig.return_config_value("mqtt_ip")
PORT = loadConfig.return_config_value("mqtt_port")
SEARCH_TOPIC = loadConfig.return_config_value("search_in_table")
ADD_TOPIC = loadConfig.return_config_value("add_to_table")
DEPTH_IMAGE_TOPIC = loadConfig.return_config_value("depth_image_topic")
COLOUR_IMAGE_TOPIC = loadConfig.return_config_value("colour_image_topic")
OUTPUT_TOPIC = loadConfig.return_config_value("matching_sku") #this should be adjusted to suit your worker requirements

DATABASE_HOST_ADDRESS = loadConfig.return_config_value("db_host_address")
USER = loadConfig.return_config_value("user")
PASSWORD = loadConfig.return_config_value("password")
DATABASE = loadConfig.return_config_value("database_name")
DATABASE_TABLE = loadConfig.return_config_value("table_name")

def search_database(db:ChurchillDatabaseActions, msg:dict):

    print(msg)
    db.add_sku(DATABASE_TABLE, msg)

def main():
    config = MQTTConfig(host=IP, port=PORT)
    db = ChurchillDatabaseActions(host=DATABASE_HOST_ADDRESS,user=USER, password=PASSWORD, database_name=DATABASE)

    client = MQTTClient(config)
    client.connect()

    search_queue = Queue()
    add_queue = Queue()
    colour_image_queue = Queue()
    depth_image_queue = Queue()

    stop_event = threading.Event()
    search_thread = start_subscribe_thread(IP, PORT, SEARCH_TOPIC, search_queue, stop_event)
    add_thread = start_subscribe_thread(IP, PORT, ADD_TOPIC, add_queue, stop_event)
    image_thread = start_subscribe_thread(IP, PORT, COLOUR_IMAGE_TOPIC, colour_image_queue, stop_event)
    depth_thread = start_subscribe_thread(IP, PORT, DEPTH_IMAGE_TOPIC, depth_image_queue, stop_event)

    try:
        while True:
            search_message = None
            add_message = None

            time.sleep(0.1)
            try:
                search_message = search_queue.get_nowait()
            except Empty:
                search_message = None

            try:
                add_message = add_queue.get_nowait()
            except Empty:
                add_message = None
                continue

            if search_message is None:
                print("Received invalid trigger payload; ignoring.")
            else:
                search_database(db, loads(search_message))

            if add_message is None:
                print("Received invalid trigger payload; ignoring.")
                continue
            else:
                print(f"message received {add_message}")
                depth_image =depth_image_queue.get(timeout=10)
                depth_image = loads(depth_image)
                add_json = loads(add_message)
                add_json["depth_data"] = {depth_image["image"]}
                colour_image = colour_image_queue.get(timeout=10)
                colour_image = loads(colour_image)
                add_json["colour_data"] = {colour_image["image"]}
                db.add_sku(DATABASE_TABLE, add_json)

    except KeyboardInterrupt:
        print("Shutting down subscribe listener and exiting.")
    finally:
        stop_event.set()
        if search_thread.is_alive():
            search_thread.join(timeout=2)
        if add_thread.is_alive():
            add_thread.join(timeout=2)

if __name__ == "__main__":
    main()