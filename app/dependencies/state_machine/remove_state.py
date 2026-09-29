from .base_functions.state import State
from logging import info

class RemoveState(State):
    ''''''
    def __init__(self, state_machine, message, state_id = "Remove State"):
        super().__init__(state_machine, state_id)
        self.message = message

    def enter(self):
        return super().enter()

    def tick(self):
        ''''''
        from .idle_state import IdleState
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
            self.my_state_machine.change_state(IdleState(self.my_state_machine))

        try:
            db[ message.get("database_name")].delete_sku(
                message.get("database_table"), 
                message.get("sku"),
                "sku"
            )

        except Exception as e:
            info(f"Error deleting data in database {e}")
            print(f"Error deleting data in database {e}")

        self.my_state_machine.change_state(IdleState(self.my_state_machine))
