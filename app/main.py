from dependencies import loadConfig
from dependencies.state_machine.database_state_machine import DatabaseStateMachine
import argparse

def main(config_path:str=""):
    config = loadConfig.get_config(config_path)
    databases_sm = DatabaseStateMachine(config)
    while True:
        databases_sm.runtime()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="get config directory")
    parser.add_argument("--config", type= str, help="the location of the config file")
    args = parser.parse_args()
    config_path = args.config
    main(config_path)