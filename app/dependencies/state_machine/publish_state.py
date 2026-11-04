from .base_functions.state import State
from mqtt_client import MQTTConnectionError
from dependencies.mqtt.mqtt_functions import packetise_results
from time import sleep
from sys import getsizeof
import logging

logger = logging.getLogger(__name__)
class PublishState(State):
    ''''''
    def __init__(self, state_machine,data:dict, state_id = "Publish State"):
        super().__init__(state_machine, state_id)
        self.data = data

    def enter(self):
        super().enter()
        if not self.my_state_machine.mqtt_client.is_connected:
            self.my_state_machine.mqtt_client.connect()
        return

    def tick(self):
        ''''''
        
        packet_list = packetise_results(
            self.data,
            self.my_state_machine.headers,
            self.my_state_machine.service_output.topic
        )
        for packet in packet_list or []:
            packet["payload"]["message_id"] = self.my_state_machine.message_id

        if packet_list == None: self.__return_idle()
        self.publish_list(packet_list)

        self.__return_idle()

    def __return_idle(self):
        from .idle_state import IdleState
        self.my_state_machine.change_state(
            IdleState(self.my_state_machine)
        )

    def publish_list(self, packet_list:list):
        '''publishes a list of packets to a given set of topics while validating each publication
        to overcome disconnect issues
        Args:
            packet_list: a list of packets and their associated dictionary of data
        '''
        for packet in packet_list:
            payload = packet.get("payload")
            topic = packet.get("topic")
            payload.pop("depth_data")
            packet_size = getsizeof(
                payload
            )
            logger.debug("Packet size %s B", packet_size)
            if not self.my_state_machine.mqtt_client.is_connected:
                self.my_state_machine.mqtt_client.connect()
            try:
                self.my_state_machine.mqtt_client.publish(
                    topic,
                    payload
                )
                # sleep(1)
                logger.info("Successfully published packet %s", topic)
            except Exception as e:
                packet_list.append(packet)
                logger.error("Failed to publish packet %s error: %s", topic, e)
                logger.info("Broker connection state: %s", self.my_state_machine.mqtt_client.is_connected)
