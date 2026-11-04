from logging import info
from abc import abstractmethod, ABC
from .state_machine import StateMachine
class State(ABC):
    '''a base class for creating new states'''
    def __init__(self, state_machine:StateMachine, state_id:str = ""):
        self.my_state_machine = state_machine
        self.state_id = state_id
        pass

    def enter(self):
        '''The entrypoint for the state, this is called first'''
        info(f"Entering {self.state_id}")
        pass

    @abstractmethod
    def tick(self):
        '''main state logic, this will run every cycle'''
        self.my_state_machine.change_state(State)

    def exit(self):
        '''the exit point for the state, this will be used to clean up'''
        info(f"Exiting {self.state_id}")
        pass
