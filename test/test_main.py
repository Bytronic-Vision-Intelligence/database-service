import json
from queue import Queue

import pytest

from fakes import FakeMQTTClient, FakeMQTTConfig, FakeThread

import main


def make_topics():
    """The shape shipped in config.example.yaml."""
    return [
        {"name": "add_to_table", "topic": "project/database/add/sku_data",
         "is_subscribe": True, "is_trigger": True},
        {"name": "search_table", "topic": "project/database/search/sku_data",
         "is_subscribe": True, "is_trigger": True},
        {"name": "database_output",
         "topic": "project/database/search/matching_sku",
         "is_subscribe": False, "is_trigger": False},
        {"name": "depth_data", "topic": "project/camera/depth/image",
         "is_subscribe": True, "is_trigger": False},
        {"name": "colour_data", "topic": "project/camera/colour_1/image",
         "is_subscribe": True, "is_trigger": False},
        {"name": "save_frame", "topic": "project/database/frame/save",
         "is_subscribe": True, "is_trigger": True},
        {"name": "frame_ack", "topic": "project/database/frame/saved",
         "is_subscribe": False, "is_trigger": False},
        {"name": "save_result", "topic": "project/database/result/save",
         "is_subscribe": True, "is_trigger": True},
        {"name": "result_ack", "topic": "project/database/result/saved",
         "is_subscribe": False, "is_trigger": False},
    ]


def subscribed(topics):
    for topic in topics:
        if topic.get("is_subscribe"):
            topic["queue"] = Queue()
    return topics


SETTINGS = {
    "image_store": "database/images",
    "frames_table": "frames",
    "results_table": "results",
    "databases": [{"database_name": "churchill_database",
                   "file_location": "database/churchill_database.db",
                   "search_threshold": 20,
                   "sku_table": "sku_table"}],
}


class FakeDatabase:
    def __init__(self, matches=None):
        # main takes the connection off the first database to create its own
        # bookkeeping tables.
        self.connection = object()
        self.matches = matches if matches is not None else [{"sku": "abc"}]
        self.added = []
        self.searched = []

    def search(self, table, message, threshold):
        self.searched.append((table, message, threshold))
        return self.matches

    def add_sku(self, table, data):
        self.added.append((table, data))


def client():
    return FakeMQTTClient(FakeMQTTConfig("127.0.0.1", 1883))


# --- the shared contract -----------------------------------------------------

def test_require_returns_the_value_when_present():
    assert main.require({"topics": []}, "topics") == []


def test_require_exits_naming_the_missing_key():
    with pytest.raises(SystemExit, match="mqtt"):
        main.require({}, "mqtt")


def test_a_section_present_but_empty_is_refused():
    """`service:` written and left blank is a section somebody meant to fill
    in. Letting it through moves the failure to whatever first subscripts it."""
    with pytest.raises(SystemExit, match="service"):
        main.require({"service": None}, "service")


def test_the_shared_helpers_match_the_template_exactly():
    """require and start_subscribers are shared verbatim by every Bytronic
    service. A local edit here is how the copies drift."""
    import ast
    import pathlib

    def source_of(path, name):
        text = pathlib.Path(path).read_text()
        for node in ast.parse(text).body:
            if isinstance(node, ast.FunctionDef) and node.name == name:
                return ast.get_source_segment(text, node)
        raise AssertionError(f"{name} not found in {path}")

    here = pathlib.Path(__file__).resolve().parent.parent
    template = here.parent / "service-template" / "app" / "main.py"
    if not template.is_file():
        pytest.skip("service-template is not checked out beside this repository")

    for name in ("require", "start_subscribers"):
        assert source_of(here / "app" / "main.py", name) == source_of(template, name)


def test_main_py_has_no_function_it_never_calls():
    import ast
    import pathlib

    tree = ast.parse((pathlib.Path(__file__).resolve().parent.parent
                      / "app" / "main.py").read_text())
    defined = {n.name for n in tree.body if isinstance(n, ast.FunctionDef)}
    called = {n.func.id for n in ast.walk(tree)
              if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}

    assert defined - called - {"main"} == set()


# --- topic_named -------------------------------------------------------------

def test_topic_named_finds_the_output_by_name_not_by_position():
    """Search results were published to the first entry with is_subscribe
    false. There are three of those, so reordering the config sent them to an
    acknowledgement topic instead."""
    topics = make_topics()
    outputs = [t["name"] for t in topics if not t["is_subscribe"]]
    assert len(outputs) == 3, "this test is pointless with only one output"

    assert (main.topic_named(topics, "database_output")["topic"]
            == "project/database/search/matching_sku")


def test_topic_named_exits_when_the_name_is_absent():
    with pytest.raises(SystemExit, match="frame_ack"):
        main.topic_named([], "frame_ack")


def test_topic_named_exits_when_the_entry_carries_no_topic():
    with pytest.raises(SystemExit, match="no `topic:` value"):
        main.topic_named([{"name": "frame_ack"}], "frame_ack")


# --- read / next_command -----------------------------------------------------

def test_read_returns_none_when_nothing_is_waiting():
    assert main.read({"topic": "t", "queue": Queue()}) is None


def test_read_discards_a_malformed_payload_without_raising(caplog):
    topic = {"topic": "t", "queue": Queue()}
    topic["queue"].put("not json at all")

    with caplog.at_level("WARNING"):
        assert main.read(topic) is None
    assert "Discarding malformed payload" in caplog.text


def test_read_with_a_timeout_returns_none_instead_of_raising():
    assert main.read({"topic": "t", "queue": Queue()}, timeout=0.01) is None


def test_next_command_returns_the_waiting_command():
    topics = subscribed(make_topics())
    main.topic_named(topics, "search_table")["queue"].put(
        '{"command": "search_phrase"}')

    assert main.next_command(topics) == {"command": "search_phrase"}


def test_next_command_ignores_the_image_feeds():
    """depth_data and colour_data are subscribed but are not triggers: they
    carry pictures continuously and must not start work."""
    topics = subscribed(make_topics())
    main.topic_named(topics, "depth_data")["queue"].put('{"image": "abc"}')

    assert main.next_command(topics) is None


def test_next_command_returns_none_when_nothing_is_waiting():
    assert main.next_command(subscribed(make_topics())) is None


# --- collect_images ----------------------------------------------------------

def test_collect_images_attaches_each_feed_by_name():
    topics = subscribed(make_topics())
    main.topic_named(topics, "depth_data")["queue"].put('{"image": "depth"}')
    main.topic_named(topics, "colour_data")["queue"].put('{"image": "colour"}')

    enriched = main.collect_images({"command": "add_phrase"}, topics)

    assert enriched["depth_data"] == "depth"
    assert enriched["colour_data"] == "colour"


def test_collect_images_leaves_the_original_command_alone():
    topics = subscribed(make_topics())
    message = {"command": "add_phrase"}

    main.collect_images(message, topics)

    assert message == {"command": "add_phrase"}


def test_a_feed_with_nothing_on_it_contributes_none():
    enriched = main.collect_images({"command": "add_phrase"},
                                   subscribed(make_topics()))

    assert enriched["depth_data"] is None


def test_an_unparseable_feed_payload_does_not_raise():
    """It reached `queue_item["image"]` on a string and raised TypeError from
    inside the handler."""
    topics = subscribed(make_topics())
    main.topic_named(topics, "depth_data")["queue"].put('"just a string"')

    assert main.collect_images({}, topics)["depth_data"] is None


# --- search / add ------------------------------------------------------------

def test_search_publishes_matches_to_the_named_output():
    topics = subscribed(make_topics())
    database = FakeDatabase(matches=[{"sku": "abc"}])
    mqtt = client()

    main.search(mqtt, main.topic_named(topics, "database_output"),
                {"database_name": "churchill_database", "destination": "sku_table"},
                {"churchill_database": database}, SETTINGS)

    topic, payload = mqtt.published[0]
    assert topic == "project/database/search/matching_sku"
    assert json.loads(payload) == [{"sku": "abc"}]


def test_search_uses_the_threshold_configured_for_that_database():
    topics = subscribed(make_topics())
    database = FakeDatabase()

    main.search(client(), main.topic_named(topics, "database_output"),
                {"database_name": "churchill_database", "destination": "sku_table"},
                {"churchill_database": database}, SETTINGS)

    assert database.searched[0][2] == 20


def test_search_against_an_unconfigured_database_warns_and_returns(caplog):
    topics = subscribed(make_topics())
    mqtt = client()

    with caplog.at_level("WARNING"):
        main.search(mqtt, main.topic_named(topics, "database_output"),
                    {"database_name": "nope", "destination": "sku_table"},
                    {}, SETTINGS)

    assert mqtt.published == []
    assert "not configured" in caplog.text


def test_add_stores_the_command_together_with_the_feeds():
    topics = subscribed(make_topics())
    main.topic_named(topics, "colour_data")["queue"].put('{"image": "colour"}')
    database = FakeDatabase()

    main.add_sku({"database_name": "churchill_database", "destination": "sku_table"},
                 topics, {"churchill_database": database})

    table, data = database.added[0]
    assert table == "sku_table"
    assert data["colour_data"] == "colour"


def test_add_against_an_unconfigured_database_warns_and_returns(caplog):
    with caplog.at_level("WARNING"):
        main.add_sku({"database_name": "nope", "destination": "t"},
                     subscribed(make_topics()), {})

    assert "not configured" in caplog.text


# --- publish -----------------------------------------------------------------

def test_publish_loses_the_message_rather_than_the_service(caplog):
    from mqtt_client.exceptions import MQTTPublishError

    class Refusing(FakeMQTTClient):
        def publish(self, topic, message):
            raise MQTTPublishError("broker gone")

    with caplog.at_level("WARNING"):
        main.publish(Refusing(FakeMQTTConfig("127.0.0.1", 1883)),
                     {"topic": "t"}, {"ok": True})

    assert "Could not publish" in caplog.text


# --- store_frame / store_result ----------------------------------------------

def test_store_frame_acknowledges_a_failure_instead_of_raising(caplog, monkeypatch):
    """The ack must go out on the failure path too, or the sender waits for an
    acknowledgement that never comes."""
    monkeypatch.setattr(main, "save_frame",
                        lambda *a, **k: (_ for _ in ()).throw(OSError("disk full")))
    topics = subscribed(make_topics())
    mqtt = client()

    with caplog.at_level("WARNING"):
        main.store_frame(mqtt, main.topic_named(topics, "frame_ack"),
                         {"camera_id": "c1"}, None, SETTINGS)

    topic, payload = mqtt.published[0]
    assert topic == "project/database/frame/saved"
    assert json.loads(payload) == {"ok": False, "error": "disk full"}
    assert "Could not save frame" in caplog.text


def test_store_result_acknowledges_a_failure_instead_of_raising(monkeypatch):
    monkeypatch.setattr(main, "save_result",
                        lambda *a, **k: (_ for _ in ()).throw(ValueError("bad row")))
    topics = subscribed(make_topics())
    mqtt = client()

    main.store_result(mqtt, main.topic_named(topics, "result_ack"),
                      {}, None, SETTINGS)

    assert json.loads(mqtt.published[0][1]) == {"ok": False, "error": "bad row"}


def test_store_frame_acknowledges_and_backfills_on_success(monkeypatch):
    monkeypatch.setattr(main, "save_frame",
                        lambda *a, **k: {"id": 7, "path": "database/images/7.png"})
    backfilled = []
    monkeypatch.setattr(main, "backfill_frame_id",
                        lambda *a, **k: backfilled.append(k) or 2)
    topics = subscribed(make_topics())
    mqtt = client()

    main.store_frame(mqtt, main.topic_named(topics, "frame_ack"),
                     {"camera_id": "c1", "date_time": "t"}, None, SETTINGS)

    assert json.loads(mqtt.published[0][1])["id"] == 7
    assert backfilled[0]["frame_id"] == 7


# --- main --------------------------------------------------------------------

def base_config(topics=None):
    return {
        "mqtt": {"mqtt_ip": "127.0.0.1", "mqtt_port": 1883,
                 "topics": topics if topics is not None else make_topics()},
        "service": dict(SETTINGS),
    }


def run_main(monkeypatch, config, feed=None, ticks_before_stop=2):
    monkeypatch.setattr(main.loadConfig, "get_config", lambda supplied=None: config)
    monkeypatch.setattr(main.logging_setup, "configure", lambda level=None: None)
    monkeypatch.setattr(main, "MQTTClient", FakeMQTTClient)
    monkeypatch.setattr(main, "MQTTConfig", FakeMQTTConfig)
    monkeypatch.setattr(main, "open_databases",
                        lambda settings: {"churchill_database": FakeDatabase()})
    monkeypatch.setattr(main, "ensure_table", lambda *a, **k: None)
    monkeypatch.setattr(main, "ensure_results_table", lambda *a, **k: None)

    threads = []
    captured = {}

    def fake_start_subscribe_thread(ip, port, topic, queue, stop_event):
        captured["stop_event"] = stop_event
        if feed and topic in feed:
            queue.put(feed[topic])
        thread = FakeThread()
        threads.append(thread)
        return thread

    monkeypatch.setattr(main, "start_subscribe_thread", fake_start_subscribe_thread)

    ticks = {"count": 0}

    def fake_sleep(_duration):
        ticks["count"] += 1
        if ticks["count"] == ticks_before_stop:
            raise KeyboardInterrupt

    monkeypatch.setattr(main.time, "sleep", fake_sleep)

    main.main(["--config", "stub.yaml"])
    return captured, threads


def test_main_dispatches_a_search_then_shuts_down_cleanly(monkeypatch):
    handled = []
    monkeypatch.setattr(main, "search",
                        lambda *a, **k: handled.append("search"))

    captured, threads = run_main(
        monkeypatch, base_config(),
        feed={"project/database/search/sku_data":
              '{"command": "search_phrase", "database_name": "churchill_database"}'})

    assert handled == ["search"]
    assert captured["stop_event"].is_set()
    assert all(thread.join_called for thread in threads)


def test_an_unknown_command_is_ignored(monkeypatch):
    for name in ("search", "add_sku", "store_frame", "store_result"):
        monkeypatch.setattr(main, name,
                            lambda *a, **k: pytest.fail("dispatched an unknown command"))

    run_main(monkeypatch, base_config(),
             feed={"project/database/add/sku_data": '{"command": "nonsense"}'},
             ticks_before_stop=3)


def test_a_failing_handler_loses_the_command_not_the_service(monkeypatch, caplog):
    monkeypatch.setattr(main, "search",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))

    with caplog.at_level("WARNING"):
        run_main(monkeypatch, base_config(),
                 feed={"project/database/search/sku_data":
                       '{"command": "search_phrase"}'},
                 ticks_before_stop=3)

    assert "failed" in caplog.text


def test_main_exits_when_a_topic_it_needs_is_missing(monkeypatch):
    topics = [t for t in make_topics() if t["name"] != "frame_ack"]
    monkeypatch.setattr(main.loadConfig, "get_config",
                        lambda supplied=None: base_config(topics))

    with pytest.raises(SystemExit, match="frame_ack"):
        main.main(["--config", "stub.yaml"])


def test_main_exits_when_a_required_key_is_missing(monkeypatch):
    monkeypatch.setattr(main.loadConfig, "get_config",
                        lambda supplied=None: {"topics": []})

    with pytest.raises(SystemExit):
        main.main(["--config", "stub.yaml"])


def test_main_configures_logging_before_it_can_fail(monkeypatch):
    import logging as _logging

    from dependencies import logging_setup

    order = []
    monkeypatch.setattr(logging_setup, "configure",
                        lambda level=None: order.append("configured"))
    monkeypatch.setattr(main.loadConfig, "get_config", lambda supplied=None: {})

    with pytest.raises(SystemExit):
        main.main(["--config", "stub.yaml"])
    assert order == ["configured"]
    _logging.getLogger().handlers[:] = _logging.getLogger().handlers


def test_main_answers_help_before_looking_for_a_config(monkeypatch):
    monkeypatch.setattr(
        main.loadConfig, "get_config",
        lambda supplied=None: pytest.fail("looked for a config before --help"))
    with pytest.raises(SystemExit) as exit_info:
        main.main(["--help"])
    assert exit_info.value.code == 0


def test_main_refuses_an_empty_config_path(monkeypatch):
    monkeypatch.setattr(main.loadConfig, "_ACTIVE", None)
    with pytest.raises(SystemExit, match="--config is required"):
        main.main(["--config", ""])


# --- what ships --------------------------------------------------------------

def shipped_config():
    from pathlib import Path

    import yaml

    return yaml.safe_load(
        (Path(__file__).resolve().parent.parent / "config.example.yaml").read_text())


def test_the_config_shipped_in_the_repo_satisfies_what_main_requires():
    config = shipped_config()
    mqtt = main.require(config, "mqtt")
    topics = main.require(mqtt, "topics")
    settings = main.require(config, "service")

    for key in ("mqtt_ip", "mqtt_port"):
        assert key in mqtt
    for key in ("image_store", "frames_table", "results_table", "databases"):
        assert key in settings, f"service.{key} missing from the shipped config"
    for name in main.REQUIRED_TOPICS:
        main.topic_named(topics, name)


def test_every_database_entry_names_its_file_and_table():
    for entry in shipped_config()["service"]["databases"]:
        for key in ("database_name", "file_location", "sku_table"):
            assert key in entry, f"databases[].{key} missing"


def test_every_topic_shares_one_namespace():
    """They carried three prefixes in one file -- churchill/, project/, and
    churchil/ with one L. The misspelled ones are why depth-analysis-service's
    search round trip went nowhere."""
    prefixes = {t["topic"].split("/")[0] for t in shipped_config()["mqtt"]["topics"]}

    assert prefixes == {"project"}, f"more than one namespace in use: {prefixes}"


def test_the_search_topics_are_the_ones_depth_analysis_uses():
    """Both halves of that exchange have to agree, and they did not."""
    topics = shipped_config()["mqtt"]["topics"]

    assert (main.topic_named(topics, "search_table")["topic"]
            == "project/database/search/sku_data")
    assert (main.topic_named(topics, "database_output")["topic"]
            == "project/database/search/matching_sku")


def test_the_release_ships_the_config_that_is_tracked():
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    workflow = (root / ".github/workflows/release-pipeline.yml").read_text(encoding="utf-8")

    assert 'cp config.example.yaml "$output_dir/config.yaml"' in workflow
    assert "/config.yaml" in (root / ".gitignore").read_text().split()


def test_the_repository_tracks_no_database_or_ci_output():
    """A live .db and junit/test-results.xml were both committed here."""
    import subprocess
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    tracked = subprocess.run(["git", "-C", str(root), "ls-files"],
                             capture_output=True, text=True).stdout.split()

    assert not [p for p in tracked if p.endswith(".db")]
    assert "junit/test-results.xml" not in tracked
    assert "config.yaml" not in tracked


def test_open_databases_creates_the_directory_it_needs(tmp_path):
    """A release bundle is the binary and its config, nothing else. sqlite
    creates the database file but not the directory holding it, so the
    packaged service exited at startup with "unable to open database file"."""
    location = tmp_path / "fresh" / "churchill_database.db"
    settings = {"databases": [{"database_name": "churchill_database",
                               "file_location": str(location),
                               "search_threshold": 20,
                               "sku_table": "sku_table"}]}

    databases = main.open_databases(settings)

    assert location.parent.is_dir()
    assert "churchill_database" in databases

