from .base_functions.state import State
from .write_state import WriteState
from logging import info

class RemoveState(State):
    '''A state to control removing data from a database by SKU'''
    def __init__(
            self, 
            state_machine, 
            message, 
            is_update=False,
            state_id = "Remove State"
        ):
        super().__init__(state_machine, state_id)
        self.message = message
        self.is_update = is_update

    def tick(self):
        '''Checks the database to ensure the SKU is present, if not returns to idle state
        if SKU is in database table, a remove request is then performed on the database'''
        message = self.message
        db = self.my_state_machine.database

        is_found = db[
            message.get("database_name")
        ].check_exists(
            "sku",message.get("sku"),
            message.get("database_table")
        )

        if not is_found: 
            info(f"Error : sku: {message.get('sku')} not found")
            print(f"Error : sku: {message.get('sku')} not found")
            self.leave_state(self.is_update, self.message)
            return

        try:
            db[ message.get("database_name")].delete_sku(
                message.get("database_table"), 
                message.get("sku"),
                "sku"
            )


        except Exception as e:
            info(f"Error deleting data in database {e}")
            print(f"Error deleting data in database {e}")

        self.leave_state(self.is_update, self.message)

    def leave_state(self, is_update, message):
        '''returns the process to the idle state and imports the idle
        state class, this cannot be done with other imports please dont move
        if the is_update flag is set, will instead move to the write state
        '''
        from .idle_state import IdleState
        if is_update:
            self.my_state_machine.change_state(
                WriteState(self.my_state_machine, message)
            )
            return
        self.my_state_machine.change_state(IdleState(self.my_state_machine))