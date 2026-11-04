from dependencies import loadConfig, logging_setup
from dependencies.state_machine.database_state_machine import DatabaseStateMachine
import argparse
import logging

logger = logging.getLogger(__name__)

def main(config_path:str=""):
    config = loadConfig.get_config(config_path)
    log_settings = config.get("logging") or {}
    logging_setup.configure(log_settings.get("level", logging_setup.DEFAULT_LEVEL))
    logger.info("%s starting", config.get('service_id', 'database_1'))
    databases_sm = DatabaseStateMachine(config)
    while True:
        databases_sm.runtime()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="get config directory")
    parser.add_argument("--config", type= str, help="the location of the config file")
    args = parser.parse_args()
    config_path = args.config
    main(config_path)
