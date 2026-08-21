from mqtt_client import MQTTClient, MQTTConfig
import threading
from queue import Queue

def subscribe_listener(ip: str, port: int, trigger_topic: str, result_queue: Queue, stop_event: threading.Event):
    '''Starts a subscriber lister thread for a given broker and topic. adds any messages to a queue.
    Args: 
        ip: a string ip address for the mqtt broker
        port: the port to access the broker connection
        trigger_topic: the topic to watch for information
        result_queue: the queue used to publish messages back to the main thread
        stop_event: the event that kills the thread (not used atm)'''
    config = MQTTConfig(host=ip, port=port)
    client = MQTTClient(config)
    client.connect()

    def _on_message(topic: str, payload: str) -> None:
        '''puts a message to the queue for the main thread to handle'''
        decoded = payload

        print("Request received:", topic)
        result_queue.put(decoded)

    client.subscribe(trigger_topic, _on_message)

def start_subscribe_thread(ip: str, port: int, topic: str, queue: Queue, stop_event: threading.Event) -> threading.Thread:
    thread = threading.Thread(
        target=subscribe_listener,
        args=(ip, port, topic, queue, stop_event),
        daemon=True,
    )
    thread.start()
    return thread