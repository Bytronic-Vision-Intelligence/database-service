"""SearchState: a search whose measurements never arrived is skipped with a clear message."""

import logging
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "app"))   # state modules import "dependencies."

from dependencies.state_machine.idle_state import IdleState  # noqa: E402
from dependencies.state_machine.search_state import SearchState  # noqa: E402


class _Machine:
    def __init__(self):
        self.blocking_subscribers = []          # nothing arrives
        self.search_headers = ["depth", "perimeter", "radius"]
        self.database = {"threshold": 2.5}
        self.mqtt_client = SimpleNamespace(publish=self._publish)
        self.service_id = "database_1"
        self.published = []
        self.states = []

    def _publish(self, topic, payload):
        self.published.append(topic)

    def change_state(self, state):
        self.states.append(state)


def test_a_search_without_measurements_is_skipped_naming_what_is_missing(caplog):
    machine = _Machine()
    message = {"database_instruction": "search", "message_id": "uid-7",
               "database_name": "test_database", "database_table": "test_table", "perimeter": 700.0}
    caplog.set_level(logging.DEBUG)

    SearchState(machine, message).tick()

    errors = [r.getMessage() for r in caplog.records if r.levelno == logging.ERROR]
    assert errors == ["Search for instruction uid-7 skipped: no depth, radius received"]
    assert machine.published == []
    assert [type(s) for s in machine.states] == [IdleState]
