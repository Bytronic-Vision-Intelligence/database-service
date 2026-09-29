from .base_functions.state import State
from dependencies.mqtt.topic import check_for_messages
from logging import info

class WriteState(State):
    ''''''
    def __init__(self, state_machine, message, state_id = "Write State"):
        super().__init__(state_machine, state_id)
        self.message = message

    def tick(self):
        ''''''
        from .idle_state import IdleState
        db = self.my_state_machine.database
        write_data = self.message
        is_duplicate = self.my_state_machine.database[
            self.message.get("database_name")
        ].check_exists(
            "sku",write_data["sku"],
            self.message.get("database_table")
        )

        if is_duplicate: 
            print(f"Error : Duplicate sku: {write_data['sku']} found")
            self.my_state_machine.change_state(IdleState(self.my_state_machine))

        for subscriber in self.my_state_machine.blocking_subscribers:
            subscriber_data=check_for_messages(subscriber)
            if "image" in subscriber_data:
                 subscriber_data[subscriber.name] = subscriber_data.pop("image")

            write_data.update(subscriber_data)

        try:
            db[ self.message.get("database_name")].add_sku(
                self.message.get("database_table"), 
                write_data,
                self.my_state_machine.headers
            )

            print(f"Info : data added to database {write_data.get('database_name')}, {write_data.get('destination')}")
        except Exception as e:
            info(f"Error transmitting data to database {e}")
            print(f"Error transmitting data to database {e}")

        self.my_state_machine.change_state(IdleState(self.my_state_machine))
        