from queue import Queue, Empty
from .mqtt_functions import start_subscribe_thread
from json import loads
from time import monotonic
import logging

logger = logging.getLogger(__name__)

class Topic():
    '''a class to host topics and their associated information making
    it easier to control multiple topics from a list'''
    def __init__(self,broker:dict, details:dict):
        self.broker = broker
        self.name = details["name"]
        self.topic = details["topic"]
        self.is_subscribe = details["is_subscribe"]
        self.is_trigger = details["is_trigger"]
        self.queue = Queue()
        self.thread = None
        self.timeout = details.get("timout", 10)
        if self.is_subscribe:
            self.__create_listener()

    def __create_listener(self):
        '''creates a listener thread and queue'''
        self.thread = start_subscribe_thread(
            self.broker["mqtt_ip"], 
            self.broker["mqtt_port"], 
            self.topic, 
            self.queue,
            None
        )


def check_for_messages(topic:Topic):
    '''Checks the queue for each of the trigger topics and returns the message when any of them have received one
    Args:
        triggers: a dictionary of topics
        is_blocking: a boolean value that controls the blocking functionality
        timout: a float that determines the timout in s
    Returns:
        message: the message received from the trigger as dictionary'''

    if not topic:
        raise ValueError("Error : trigger cannot be empty")
    message = {"image": None}

    if topic.is_subscribe and not topic.is_trigger:
        try:
            message = loads(topic.queue.get(block = True, timeout=topic.timeout))
            return message
        except Exception as e:
            if e != KeyError: info(f"error occured when checking for trigger {e}")
    
    try:
        message = loads(topic.queue.get_nowait())
    except Exception as e:
        if e != KeyError: info(f"error occured when checking for trigger {e}")

    return message


def check_for_matching_message(topic:Topic, message_id:str=None):
    '''Waits on a blocking topic for the message captured for this instruction, discarding any
    left over from earlier instructions so a cycle never searches with a previous cycle's data
    Args:
        topic: a blocking (subscribe, not trigger) topic
        message_id: the message_id of the instruction being served, None reads the next message
    Returns:
        message: the matching message as a dictionary, or {"image": None} on timeout'''
    if message_id is None:
        return check_for_messages(topic)

    deadline = monotonic() + topic.timeout
    while True:
        remaining = deadline - monotonic()
        if remaining <= 0:
            logger.warning("No message for %s on %s within %s s", message_id, topic.topic, topic.timeout)
            return {"image": None}
        try:
            message = loads(topic.queue.get(block = True, timeout=remaining))
        except Empty:
            continue
        if message.get("message_id") == message_id:
            return message
        logger.info("Discarding stale message %s on %s, waiting for %s", message.get('message_id'), topic.topic, message_id)
