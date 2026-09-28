from state import State
from search_state import SearchState
from write_state import WriteState

from database_state_machine import DatabaseStateMachine
from dependencies.mqtt.mqtt_functions import *

class IdleState(State):
    ''''''
    def __init__(
            self, 
            state_machine:DatabaseStateMachine,
            state_id:str = "Idle state"):
        self.my_state_machine = state_machine
        self.state_id = state_id

    def tick(self):
        ''''''
        message = check_for_messages(self.my_state_machine.ui_request)
        instruction = message.get("database_instruction")
        if instruction == None: return

        if instruction == "search_database":
            self.my_state_machine.change_state(SearchState)
        if instruction == "write_database":
            self.my_state_machine.change_state(WriteState)
        if instruction == "remove_sku":
            self.my_state_machine.change_state()
        if instruction == "update_sku":
            self.my_state_machine.change_state()
