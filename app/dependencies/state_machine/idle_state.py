from .base_functions.state import State
from .search_state import SearchState
from .write_state import WriteState
from .remove_state import RemoveState
from .update_state import UpdateState
from dependencies.mqtt.mqtt_functions import *
from dependencies.mqtt.topic import check_for_messages

class IdleState(State):
    '''A state to control the idle process'''
    def __init__(self, state_machine, state_id = "Idle State"):
        super().__init__(state_machine, state_id)

    def tick(self):
        '''Waits for a message to be received from the UI, then switches to the appropriate
        state based on the given command found under the database_instruction key'''
        message = check_for_messages(self.my_state_machine.ui_request)
        instruction = message.get("database_instruction")
        if instruction == None: return

        if instruction == "search_database":
            self.my_state_machine.change_state(SearchState(
                self.my_state_machine, message
            ))
        if instruction == "write_database":
            self.my_state_machine.change_state(WriteState(
                self.my_state_machine, message
            ))
        if instruction == "remove_sku":
            self.my_state_machine.change_state(RemoveState(
                self.my_state_machine, message
            ))
        if instruction == "update_sku":
            self.my_state_machine.change_state(UpdateState(
                self.my_state_machine, message
            ))