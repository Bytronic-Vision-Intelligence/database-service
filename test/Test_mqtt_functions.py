import importlib.util
import sys
import types
import pathlib
import threading
from queue import Queue
import uuid

ROOT = pathlib.Path(__file__).resolve().parent.parent
APP_DIR = ROOT / "app"
sys.path.insert(0, str(APP_DIR))


def load_main_module(config_values=None):
    if config_values is None:
        config_values = {
            "ip": "127.0.0.1",
            "port": 1883,
            "trigger_topic": "test/topic",
            "output_topic": "test/output",
        }

    fake_loadConfig = types.ModuleType("dependencies.loadConfig")

    def return_config_value(key):
        if not key:
            raise ValueError("Key cannot be empty.")
        if key not in config_values:
            raise KeyError(f"Key '{key}' not found in configuration.")
        return config_values[key]

    def get_config():
        return config_values

    fake_loadConfig.return_config_value = return_config_value
    fake_loadConfig.get_config = get_config

    fake_pkg = types.ModuleType("dependencies")
    fake_pkg.loadConfig = fake_loadConfig

    sys.modules["dependencies"] = fake_pkg
    sys.modules["dependencies.loadConfig"] = fake_loadConfig

    spec_name = f"main_mod_{uuid.uuid4().hex}"
    spec = importlib.util.spec_from_file_location(spec_name, APP_DIR / "main.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec_name] = module
    spec.loader.exec_module(module)
    return module


class FakeMQTTClient:
    def __init__(self, config):
        self.config = config
        self.connected = False
        self.subscriptions = []

    def connect(self):
        self.connected = True

    def subscribe(self, topic, callback):
        self.subscriptions.append((topic, callback))
        payload = {
            "image":None,
            "date_time":None
        }
        callback(payload)


class FakeMQTTConfig:
    def __init__(self, host, port):
        self.host = host
        self.port = port


class FakeThread:
    def __init__(self):
        self.join_called = False
        self.alive = True

    def is_alive(self):
        return self.alive

    def join(self, timeout=None):
        self.join_called = True
        self.alive = False