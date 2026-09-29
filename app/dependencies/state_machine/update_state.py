from dependencies.state_machine.base_functions.state import State
from .remove_state import RemoveState
class UpdateState(State):
    '''A state to control updating SKU data in a database'''
    def __init__(self, state_machine,message, state_id = "Update State"):
        super().__init__(state_machine, state_id)
        self.message = message

    def tick(self):
        '''moves to the remove state while setting the flag to force the remove
        state to then transfer to the write state'''
        self.my_state_machine.change_state(
            RemoveState(
                self.my_state_machine,
                self.message, 
                True
            )
        )

    def return_to_idle(self):
        '''returns the process to the idle state and imports the idle
        state class, this cannot be done with other imports
        please dont move
        '''
        from .idle_state import IdleState
        self.my_state_machine.change_state(IdleState(
            self.my_state_machine
        ))