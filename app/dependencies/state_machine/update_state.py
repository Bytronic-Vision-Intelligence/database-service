from dependencies.state_machine.base_functions.state import State
from dependencies.state_machine.write_state import WriteState
from dependencies.database_actions.mysql_database_actions import MysqlDatabaseActions
from dependencies.mqtt.topic import check_for_messages
from datetime import datetime
from logging import info

class UpdateState(State):
    '''A state to control updating SKU data in a database'''
    def __init__(self, state_machine,message, state_id = "Update State"):
        super().__init__(state_machine, state_id)
        self.message = message

    def tick(self):
        '''checks for a duplicate item, if found updates the item, if not moves to the 
        write state to add it to the database'''
        db:MysqlDatabaseActions = self.my_state_machine.database
        update_data = self.message

        is_duplicate = self.my_state_machine.database[
            self.message.get("database_name")
        ].check_exists(
            "sku",update_data["sku"],
            self.message.get("database_table")
        )

        if not is_duplicate: 
            print(f"Error : No sku: {update_data['sku']} found")
            self.my_state_machine.change_state(
                WriteState(
                    self.my_state_machine,
                    self.message
                )
            )
            return

        for subscriber in self.my_state_machine.blocking_subscribers:
            subscriber_data=check_for_messages(subscriber)
            if "image" in subscriber_data:
                    subscriber_data[subscriber.name] = subscriber_data.pop("image")
            subscriber_data["date_added"] = datetime.now()
            update_data.update(subscriber_data)

        try:
            db[ self.message.get("database_name")].update_sku(
                self.message.get("database_table"), 
                update_data,
                self.my_state_machine.headers
            )

            print(f"Info : data updated {update_data.get('database_name')}, {update_data.get('destination')}")
        except Exception as e:
            info(f"Error transmitting data to database {e}")
            print(f"Error transmitting data to database {e}")

        self.return_to_idle()

    def return_to_idle(self):
        '''returns the process to the idle state and imports the idle
        state class, this cannot be done with other imports
        please dont move
        '''
        from .idle_state import IdleState
        self.my_state_machine.change_state(IdleState(
            self.my_state_machine
        ))