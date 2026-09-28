from .state_machine import StateMachine
from dependencies.mqtt.mqtt_functions import *
from dependencies.database_actions.sqlite_database_actions import SqliteDatabaseActions

class DatabaseStateMachine(StateMachine):
    def __init__(self, config:dict):
        super().__init__()
        self.service_id = config.get("service_id", "database_1")
        self.mqtt_client = self.__create_mqtt_client(config)
        self.topics = create_topic_listners(config)
        self.database, self.headers, self.search_headers = self.__setup_database(config)
        self.ui_request = self.__get_topic(self.topics,"hmi_request")
        self.service_output = self.__get_topic(self.topics, "database_output")
        self.blocking_subscribers = self.__get_blocking_subscribers(self.topics)
    
    def publish_message(
            self, 
            payload = any, 
            topic = None, 
            is_many:bool = False
        ):
        '''publishes a message using the connected client
        Args:
            payload: this can be a list of dicts for many or a string
            topic: this is the topic if sending single items
            is_many: a selector to choose the type of publish to use'''
        if is_many: 
            self.mqtt_client.publish_many(payload)
            return
        self.mqtt_client.publish(topic, payload)

    @staticmethod
    def __create_mqtt_client(config:dict):
        '''creates an mqtt client object from the config'''
        broker_details = config.get("broker_details")
        
        mqtt_config = MQTTConfig(
            host=broker_details["mqtt_ip"], 
            port=broker_details["mqtt_port"]
        )
        client = MQTTClient(mqtt_config)
        client.connect()
        return client

    @staticmethod
    def __setup_database(client:dict):
        '''used to setup a database'''
        database = client.get("database")
        db = {database["database_name"]: SqliteDatabaseActions(
            database_location=database["file_location"]
        )}
        table_name = database["tables"][0]["database_table"]
        headers = database["tables"][0]["columns"]
        search_headers = database["tables"][0]["searchable_columns"]
        print(headers)
        if not db[database["database_name"]].check_table_exists(table_name):
            raise ConnectionError(f"Error : Could not connect to table {table_name}")
        db[database["database_name"]].set_database_map(table_name)
        db["threshold"]=database["search_threshold"]
        return db, headers, search_headers

    @staticmethod
    def __get_topic(topic_dict:dict, topic_name:str):
        '''returns the topic associated with the key value
        Args:
            topic_dict: a dictionary of topics, one value needs to be "name"
            topic_name: the name to search within the topic list
        Returns:
            the topic object accosiated with the name
        '''
        return next((t for t in topic_dict if t.get("name") == topic_name), None)

    @staticmethod
    def __get_blocking_subscribers(topics):
        '''returns a list of topics that are not triggers and will block
        functionality until data is received
        Args:
            config: the microservice config containing a correctly formatted topics section
        returns
            a list of topics
        '''
        blocking_subscribers = []
        for topic in topics:
            if not topic.is_subscribe or topic.is_trigger: continue
            blocking_subscribers.append(topic)
        return blocking_subscribers

