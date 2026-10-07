import threading
from queue import Queue
from logging import info

from mqtt_client import MQTTClient, MQTTConfig

def subscribe_listener(ip: str, port: int, trigger_topic: str, result_queue: Queue, stop_event: threading.Event):
    """Connect to a broker and feed every message on `trigger_topic` into a queue.

    Args:
        ip: broker address.
        port: broker port.
        trigger_topic: the topic to watch.
        result_queue: queue used to hand payloads back to the main thread.
        stop_event: shared shutdown signal (reserved; the client owns its loop).
    """
    config = MQTTConfig(host=ip, port=port)
    client = MQTTClient(config)
    client.connect()

    def _on_message(topic: str, payload: str) -> None:
        """Hand a received payload to the main thread."""
        info("Request received:", topic)
        result_queue.put(payload)

    client.subscribe(trigger_topic, _on_message)

def start_subscribe_thread(ip: str, port: int, topic: str, queue: Queue, stop_event: threading.Event) -> threading.Thread:
    """Run `subscribe_listener` on a daemon thread.

    Args:
        ip: broker address.
        port: broker port.
        topic: the topic to watch.
        queue: queue used to hand payloads back to the main thread.
        stop_event: shared shutdown signal.
    Returns:
        thread: the started daemon thread.
    """
    thread = threading.Thread(
        target=subscribe_listener,
        args=(ip, port, topic, queue, stop_event),
        daemon=True,
    )
    thread.start()
    return thread

def create_subtopic_listners(
        subtopic_count:int, 
        topic:str, 
        name:str,
        broker_info:dict
    ):
    '''creates listners for a set of subtopics and returns a list of those subtopics
    Args:
        subtopic_count: the number of subtopics to create as an int
        topic: a string containing the main topic
        name: a string containing the topic identifier
        broker_info: a dictionary containing the ip address and the port for the broker
    Returns:
        a list of subtopics
    '''
    subtopic_list = []
    for i in range(0,subtopic_count):
        sub_topic = f"{topic}/{i}"
        sub_name = f"{name}_{i}",
        subtopic={
            **topic,
            "name": sub_topic,
            "topic": sub_name,
            "queue": Queue()
        }

        subtopic["thread"] = start_subscribe_thread(
            broker_info["mqtt_ip"], 
            broker_info["mqtt_port"], 
            subtopic["topic"], 
            subtopic["queue"],
            None
        )
        subtopic_list.append(subtopic)
        subtopic = None
    return subtopic_list

def packetize_results(results:dict, results_map:list[str], topic:str):
    '''splits results into packets and then wraps then appropriately for publication
    Args:
        results: a ditionary of results
        results_map: a list of strings containing relevent headings
    Returns:
        a list of dictionaries containing the topic to publish on and the data to publish
    '''
    if type(results)!= dict:
        raise TypeError(f"Error : results must be a dictionary")
    packet_list = []
    packet_number = 0
    for candidate in results:
        if results[candidate].get("database_response") != None: 
            info(f"Error : No matches found, aborting packetization")
            return
        packet = dict()
        packet["topic"] = f"{topic}/{packet_number}"
        packet["payload"] = {
            "packet_number": packet_number,
        }
        for item in results_map:
            packet["payload"][item] = results[candidate].get(item)
        packet_number+=1
        packet_list.append(packet)
    return packet_list