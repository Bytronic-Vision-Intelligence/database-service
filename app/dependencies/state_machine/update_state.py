from dependencies.state_machine.base_functions.state import State
from .remove_state import RemoveState
class UpdateState(State):
    ''''''
    def __init__(self, state_machine,message, state_id = "Update State"):
        super().__init__(state_machine, state_id)
        self.message = message

    def enter(self):
        ''''''

    def tick(self):
        ''''''
        self.my_state_machine.change_state(
            RemoveState(
                self.my_state_machine,
                self.message, 
                True
            )
        )
    def exit(self):
        ''''''

    def return_to_idle(self):
        from .idle_state import IdleState
        self.my_state_machine.change_state(IdleState(
            self.my_state_machine
        ))