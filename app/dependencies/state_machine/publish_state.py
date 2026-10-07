from .base_functions.state import State
from dependencies.mqtt.mqtt_functions import packetize_results

class PublishState(State):
    ''''''
    def __init__(self, state_machine,data:dict, state_id = "Publish State"):
        super().__init__(state_machine, state_id)
        self.data = data

    def tick(self):
        ''''''
        packet_list = packetize_results(
            self.data,
            self.my_state_machine.headers,
            self.my_state_machine.service_output.topic
        )
        if packet_list != None:
            self.my_state_machine.mqtt_client.publish_many(packet_list)

        self.__return_idle()

    def __return_idle(self):
        from .idle_state import IdleState
        self.my_state_machine.change_state(
            IdleState(self.my_state_machine)
        )