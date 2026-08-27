"""Shared broker fakes, so the suite runs without an MQTT broker."""


class FakeMQTTConfig:
    def __init__(self, host, port):
        self.host = host
        self.port = port


class FakeMQTTClient:
    """Delivers one payload straight back through subscribe(), no network."""

    def __init__(self, config, payload='{"command": "search_phrase"}'):
        self.config = config
        self.connected = False
        self.subscriptions = []
        self.published = []
        self.payload = payload

    def connect(self):
        self.connected = True

    def subscribe(self, topic, callback):
        self.subscriptions.append((topic, callback))
        callback(topic, self.payload)

    def publish(self, topic, message):
        self.published.append((topic, message))
