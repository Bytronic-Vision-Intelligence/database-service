"""check_for_messages: an empty queue is the normal idle case, a bad message is skipped."""

import logging
from queue import Queue
from types import SimpleNamespace

from app.dependencies.mqtt.topic import check_for_messages


def _topic(*payloads, is_trigger=True, timeout=0.01):
    queue = Queue()
    for payload in payloads:
        queue.put(payload)
    return SimpleNamespace(topic="project/test", queue=queue, is_subscribe=True, is_trigger=is_trigger, timeout=timeout)


def test_an_empty_trigger_queue_returns_the_default_and_logs_nothing(caplog):
    caplog.set_level(logging.DEBUG)

    message = check_for_messages(_topic())

    assert message == {"image": None}
    assert caplog.records == []


def test_a_waiting_message_is_returned():
    message = check_for_messages(_topic('{"command": "search_phrase"}'))

    assert message == {"command": "search_phrase"}


def test_an_unreadable_message_is_skipped_with_a_warning(caplog):
    caplog.set_level(logging.DEBUG)

    message = check_for_messages(_topic("not json"))

    assert message == {"image": None}
    assert [r.levelname for r in caplog.records] == ["WARNING"]


def test_a_blocking_topic_that_times_out_warns_once(caplog):
    caplog.set_level(logging.DEBUG)

    message = check_for_messages(_topic(is_trigger=False))

    assert message == {"image": None}
    assert [r.levelname for r in caplog.records] == ["WARNING"]
