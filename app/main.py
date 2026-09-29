from dependencies import loadConfig
from dependencies.state_machine.database_state_machine import DatabaseStateMachine

def main():
    config = loadConfig.get_config()
    databases_sm = DatabaseStateMachine(config)
    while True:
        databases_sm.runtime()

if __name__ == "__main__":
    main()