from dependencies import loadConfig
from dependencies.state_machine.database_state_machine import DatabaseStateMachine
#
MQTT_BROKERS = loadConfig.return_config_value("broker_details")
TOPICS = loadConfig.return_config_value("topics")
DATABASE_DETAILS = loadConfig.return_config_value("database")

def main():
    config = loadConfig.get_config()
    databases_sm = DatabaseStateMachine(config)
    while True:
        databases_sm.runtime()

if __name__ == "__main__":
    main()