from .base_functions.state import State
from dependencies.mqtt.mqtt_functions import MQTTClient, packetize_results
from dependencies.database_actions.sqlite_database_actions import SqliteDatabaseActions
from dependencies.mqtt.topic import check_for_messages
from logging import info
from json import dumps
class SearchState(State):
    ''''''
    def __init__(self, state_machine, message, state_id = "Search State"):
        super().__init__(state_machine, state_id)
        self.message = message

    def tick(self):
        ''''''
        try:
            search_data = self.message
            for subscriber in self.my_state_machine.blocking_subscribers:
                search_data.update(check_for_messages(subscriber))

            self._fuzzy_search_database(
                self.my_state_machine.mqtt_client, 
                search_data, 
                self.my_state_machine.database, 
                self.my_state_machine.search_headers,
                self.my_state_machine.database["threshold"]
            )

        except Exception as e:
            info(f"Error : {self.my_state_machine.service_id} fuzzy search failed: {e}")
            print(f"Error : {self.my_state_machine.service_id} fuzzy search failed: {e}")

        from .idle_state import IdleState
        self.my_state_machine.change_state(IdleState(self.my_state_machine))

    def _fuzzy_search_database(self,
        client:MQTTClient, 
        message:dict, 
        db:SqliteDatabaseActions,
        headers,
        threshold:float=0
    ):
        '''performs a fuzzy search on the current database and publishes the results to a given MQTT broker
        Args:
            client: an MQTT client object
            message: a dict containing a search term
            db: a database actions object
        '''
        response = dict()

        if client is None: raise ValueError("Error: client cannot be None")
        if message is None: raise ValueError("Error: message cannot be empty")
        if db is None: raise ValueError("Error: no database object detected")

        database_name = message.get("database_name")
        if database_name == None: raise ValueError(f"Error : database name cannot be None")
        table_name = message.get("database_table")
        if table_name == None: raise ValueError(f"Error : table name cannot be None")
        
        search_results = db[database_name].search(table_name, message,headers, threshold)
        response["matches_found"]=len(search_results)
        client.publish(
            f"{self.my_state_machine.service_output.topic}", 
            dumps(response)
        )
        
        if len(search_results) == 0:return

        packet_list = packetize_results(search_results)
        client.publish_many(packet_list)