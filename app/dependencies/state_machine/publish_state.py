from .base_functions.state import State
from mqtt_client import MQTTConnectionError
from dependencies.mqtt.mqtt_functions import packetise_results
from logging import info
from time import sleep
from sys import getsizeof
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
            print(f"Info : packet size {packet_size} B")
            if not self.my_state_machine.mqtt_client.is_connected:
                self.my_state_machine.mqtt_client.connect()
            try:
                self.my_state_machine.mqtt_client.publish(
                    topic,
                    payload
                )
                # sleep(1)
                print(f"Info : successfully published packet {topic}")
            except Exception as e:
                packet_list.append(packet)
                print(f"Error : failed to publish packet {topic} error: {e}")
                print(f"Info : broker connection state: {self.my_state_machine.mqtt_client.is_connected}")