from json import dumps
from queue import Queue

import pytest

import main


def make_topics():
    """Mirrors the shape in app/dependencies/config.yaml."""
    return [
        {"name": "add_to_table", "topic": "db/add/sku", "is_subscribe": True, "is_trigger": True},
        {"name": "search_table", "topic": "db/search/sku", "is_subscribe": True, "is_trigger": True},
        {"name": "db_output", "topic": "db/search/match", "is_subscribe": False, "is_trigger": False},
        {"name": "depth", "topic": "depth/image", "is_subscribe": True, "is_trigger": False},
    ]


def test_require_returns_the_value_when_present():
    assert main.require({"topics": []}, "topics") == []


def test_require_exits_naming_the_missing_key():
    with pytest.raises(SystemExit) as excinfo:
        main.require({}, "broker_details")

    assert "broker_details" in str(excinfo.value)


def test_check_for_triggers_returns_a_null_command_when_nothing_waiting():
    topics = make_topics()
    for topic in topics:
        topic["queue"] = Queue()

    assert main._check_for_triggers(topics)["command"] is None


def test_check_for_triggers_decodes_a_waiting_trigger():
    topics = make_topics()
    for topic in topics:
        topic["queue"] = Queue()
    topics[1]["queue"].put(dumps({"command": "search_phrase", "diameter": 100.0}))

    message = main._check_for_triggers(topics)

    assert message["command"] == "search_phrase"
    assert message["diameter"] == 100.0


def test_check_for_triggers_ignores_topics_that_are_not_triggers():
    topics = make_topics()
    for topic in topics:
        topic["queue"] = Queue()
    # depth is is_trigger False - a message here must not start work
    topics[3]["queue"].put(dumps({"command": "search_phrase"}))

    assert main._check_for_triggers(topics)["command"] is None


def test_fuzzy_search_publishes_to_the_unsubscribed_topic():
    topics = make_topics()

    class FakeDb:
        def search(self, destination, message, threshold):
            return {0: {"id": 1, "diameter": 100.0}}

    published = []

    class FakeClient:
        def publish(self, topic, payload):
            published.append((topic, payload))

    message = {"command": "search_phrase", "database_name": "d", "destination": "sku_table"}
    main._fuzzy_search_database(FakeClient(), message, {"d": FakeDb()}, topics, 20)

    assert published[0][0] == "db/search/match"
    assert '"diameter": 100.0' in published[0][1]


def test_fuzzy_search_rejects_missing_arguments():
    topics = make_topics()
    with pytest.raises(ValueError):
        main._fuzzy_search_database(None, {"a": 1}, {"d": object()}, topics)
    with pytest.raises(ValueError):
        main._fuzzy_search_database(object(), None, {"d": object()}, topics)
    with pytest.raises(ValueError):
        main._fuzzy_search_database(object(), {"a": 1}, None, topics)


def test_wait_for_data_rejects_an_empty_message():
    with pytest.raises(ValueError):
        main._wait_for_data(None, make_topics())
