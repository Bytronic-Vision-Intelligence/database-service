import time
from json import JSONDecodeError, dumps, loads
from logging import info, warning
from pathlib import Path
from queue import Empty, Queue
from threading import Event

from mqtt_client import MQTTClient, MQTTConfig
from mqtt_client.exceptions import MQTTClientError

from dependencies import loadConfig, logging_setup
from dependencies.frame_store import ensure_table, save_frame
from dependencies.mqtt_functions import start_subscribe_thread
from dependencies.result_store import (
    backfill_frame_id,
    ensure_table as ensure_results_table,
    save_result,
)
from dependencies.seed import seed_database
from dependencies.sqlite_database_actions import SqliteDatabaseActions

#: How long to wait for each image feed when an add command needs one. Not a
#: deployment setting: it paces one exchange inside a single command, and a
#: feed that has published nothing recently simply contributes nothing.
IMAGE_WAIT = 1

#: Topics this service reads or publishes, resolved at startup so a renamed
#: entry refuses there rather than going quiet at the first message.
REQUIRED_TOPICS = (
    "add_to_table", "search_table", "database_output",
    "save_frame", "frame_ack", "save_result", "result_ack",
)


def require(config: dict, key: str):
    """Return a required top-level config value, or exit describing what is missing.

    Args:
        config: the loaded configuration mapping.
        key: the top-level key the service cannot start without.
    Returns:
        the value stored under `key`.
    Raises:
        SystemExit: when `key` is absent, naming both the key and the file.
    """
    # `is None` as well as absent: a key present but empty is a section
    # somebody meant to fill in, and letting it through moves the failure to
    # whatever first subscripts it.
    if key not in config or config[key] is None:
        # Named only if one has been loaded. require() is also called on
        # nested sections in contexts that never parsed arguments, and
        # config_path() refuses to guess there -- which would replace this
        # message with one about the wrong problem entirely.
        try:
            where = f" in {loadConfig.config_path()}"
        except SystemExit:
            where = ""
        raise SystemExit(f"Missing required config key '{key}'{where}")
    return config[key]


def start_subscribers(mqtt_config: dict, topics: list, stop_event: Event) -> list:
    """Start one listener thread per subscribed topic.

    Each topic entry with `is_subscribe` true gains a `queue` key, which
    `next_trigger` later reads from.

    Args:
        mqtt_config: the `mqtt` section, carrying mqtt_ip and mqtt_port.
        topics: configured topic entries; mutated in place to carry queues.
        stop_event: shared shutdown signal handed to every listener.
    Returns:
        threads: the started listener threads.
    """
    threads = []
    for topic in topics:
        if not topic.get("is_subscribe"):
            continue
        topic["queue"] = Queue()
        threads.append(
            start_subscribe_thread(
                mqtt_config["mqtt_ip"],
                mqtt_config["mqtt_port"],
                topic["topic"],
                topic["queue"],
                stop_event,
            )
        )
    return threads


def topic_named(topics: list, name: str) -> dict:
    """Return the configured topic entry called `name`.

    Args:
        topics: the `mqtt.topics` entries.
        name: the `name:` to find.
    Returns:
        the entry itself, so callers can reach both its topic and its queue.
    Raises:
        SystemExit: when no entry carries that name, or it carries no topic.
            Search results used to be published to the first entry with
            `is_subscribe: false`, of which there are three -- so reordering
            the config sent them to an acknowledgement topic instead.
    """
    for topic in topics:
        if topic.get("name") != name:
            continue
        if not topic.get("topic"):
            raise SystemExit(f"Topic '{name}' has no `topic:` value")
        return topic
    raise SystemExit(
        f"No topic named '{name}'. database-service looks its topics up by "
        f"name; add `- name: {name}` under mqtt.topics.")


def read(topic: dict, timeout: float = None):
    """Return the next payload waiting on one topic, or None.

    Args:
        topic: a subscribed topic entry, after `start_subscribers` has run.
        timeout: seconds to wait. None returns immediately.
    Returns:
        message: the decoded payload, or None when nothing arrived in time or
            the payload was not valid JSON.
    """
    try:
        if timeout:
            payload = topic["queue"].get(timeout=timeout)
        else:
            payload = topic["queue"].get_nowait()
    except Empty:
        return None
    try:
        return loads(payload)
    except (JSONDecodeError, TypeError) as exc:
        warning(f"Discarding malformed payload on {topic['topic']}: {exc}")
        return None


def next_command(topics: list):
    """Return the next command waiting on any trigger topic.

    Args:
        topics: configured topic entries, after `start_subscribers` has run.
    Returns:
        the decoded command, or None when no trigger is waiting.
    """
    for topic in topics:
        if not topic.get("is_trigger") or "queue" not in topic:
            continue
        message = read(topic)
        if message is not None:
            return message
    return None


def collect_images(message: dict, topics: list) -> dict:
    """Attach the latest frame from each image feed to an add command.

    The feeds are the subscribed topics that are not triggers: they carry
    pictures continuously and none of them starts work on its own.

    Args:
        message: the add command.
        topics: configured topic entries.
    Returns:
        a copy of the command with one key per feed, holding its image or None.
    """
    enriched = dict(message)
    for topic in topics:
        if not topic.get("is_subscribe") or topic.get("is_trigger"):
            continue
        payload = read(topic, timeout=IMAGE_WAIT)
        # A feed that published nothing recently contributes None rather than
        # stopping the command. Previously an unparseable payload reached
        # `queue_item["image"]` and raised TypeError from inside the handler.
        enriched[topic["name"]] = (
            payload.get("image") if isinstance(payload, dict) else None)
    return enriched


def open_databases(settings: dict) -> dict:
    """Open every configured database and return them by name.

    Args:
        settings: the `service` section, carrying the `databases` list.
    Returns:
        the opened databases, keyed by `database_name`.
    Raises:
        SystemExit: when a configured table is not there after seeding. The
            service cannot answer a search against a table that does not
            exist, so it says so at startup.
    """
    databases = {}
    for entry in settings["databases"]:
        location = Path(entry["file_location"])
        # sqlite creates the file but not the directory holding it, and a
        # release bundle is just the binary and its config -- so the packaged
        # service died on startup with "unable to open database file" before
        # this. frame_store does the same for the image store.
        location.parent.mkdir(parents=True, exist_ok=True)

        actions = SqliteDatabaseActions(database_location=str(location))
        # The .db is gitignored, so a fresh checkout starts with an empty file.
        # Seed it before the existence check below.
        seed_database(actions.connection)

        table = entry["sku_table"]
        if not actions.check_table_exists(table):
            raise SystemExit(
                f"Table '{table}' is not in {entry['file_location']}")
        actions.set_database_map(table)
        databases[entry["database_name"]] = actions
    return databases


def search(client: MQTTClient, output: dict, message: dict,
           databases: dict, settings: dict) -> None:
    """Answer a search and publish the matches.

    Args:
        client: connected MQTT client.
        output: the topic entry to publish matches to.
        message: the command, naming the database, the table and the terms.
        databases: the opened databases, by name.
        settings: the `service` section, carrying each database's threshold.
    """
    name = message.get("database_name")
    database = databases.get(name)
    if database is None:
        warning(f"Search names database '{name}', which is not configured")
        return

    threshold = next((entry.get("search_threshold", 0)
                      for entry in settings["databases"]
                      if entry["database_name"] == name), 0)

    matches = database.search(message["destination"], message, threshold)
    info("Search on %s returned %s row(s)", message["destination"], len(matches))
    publish(client, output, matches)


def add_sku(message: dict, topics: list, databases: dict) -> None:
    """Add a row, with whatever the image feeds are currently showing.

    Args:
        message: the command, naming the database and the table.
        topics: configured topic entries, read for the image feeds.
        databases: the opened databases, by name.
    """
    name = message.get("database_name")
    database = databases.get(name)
    if database is None:
        warning(f"Add names database '{name}', which is not configured")
        return

    database.add_sku(message["destination"], collect_images(message, topics))
    info("Added a row to %s", message["destination"])


def store_frame(client: MQTTClient, ack: dict, message: dict,
                connection, settings: dict) -> None:
    """Save a captured frame and acknowledge it.

    Args:
        client: connected MQTT client.
        ack: the topic entry to acknowledge on.
        message: the save command, carrying the image and its metadata.
        connection: the open sqlite3 connection.
        settings: the `service` section, naming the tables and the image store.
    """
    try:
        result = save_frame(
            message,
            image_store=Path(settings["image_store"]),
            connection=connection,
            table=settings["frames_table"],
        )
    except Exception as exc:
        warning(f"Could not save frame: {exc}")
        publish(client, ack, {"ok": False, "error": str(exc)})
        return

    publish(client, ack, result)
    linked = backfill_frame_id(
        connection,
        camera_id=str(message.get("camera_id") or "unknown"),
        ts=str(message.get("date_time") or ""),
        frame_id=result["id"],
        table=settings["results_table"],
    )
    if linked:
        info("Back-filled %s result(s) with frame %s", linked, result["id"])
    info("Saved frame %s to %s", result["id"], result["path"])


def store_result(client: MQTTClient, ack: dict, message: dict,
                 connection, settings: dict) -> None:
    """Save an inference result and acknowledge it.

    Args:
        client: connected MQTT client.
        ack: the topic entry to acknowledge on.
        message: the save command.
        connection: the open sqlite3 connection.
        settings: the `service` section, naming the tables.
    """
    try:
        result = save_result(
            message,
            connection=connection,
            table=settings["results_table"],
            frames_table=settings["frames_table"],
        )
    except Exception as exc:
        warning(f"Could not save result: {exc}")
        publish(client, ack, {"ok": False, "error": str(exc)})
        return

    publish(client, ack, result)
    info("Saved result %s (frame %s)", result["id"], result["frame_id"])


def publish(client: MQTTClient, topic: dict, payload) -> None:
    """Publish one message, losing it rather than the service if the broker refuses.

    Args:
        client: connected MQTT client.
        topic: the topic entry to publish to.
        payload: anything json.dumps accepts.
    """
    try:
        client.publish(topic["topic"], dumps(payload))
    except MQTTClientError as exc:
        warning(f"Could not publish to {topic['topic']}: {exc}")


def main(argv=None):
    args = loadConfig.parse_cli(argv)

    config = loadConfig.get_config(args.config)

    log_settings = config.get("logging") or {}
    logging_setup.configure(log_settings.get("level", logging_setup.DEFAULT_LEVEL))

    mqtt_config = require(config, "mqtt")
    topics = require(mqtt_config, "topics")
    settings = require(config, "service")
    require(settings, "databases")

    named = {name: topic_named(topics, name) for name in REQUIRED_TOPICS}

    databases = open_databases(settings)
    connection = next(iter(databases.values())).connection
    # Created if absent rather than being fatal, unlike the sku_table check in
    # open_databases: these two are this service's own bookkeeping.
    ensure_table(connection, settings["frames_table"])
    ensure_results_table(connection, settings["results_table"])

    client = MQTTClient(
        MQTTConfig(host=mqtt_config["mqtt_ip"], port=mqtt_config["mqtt_port"]))
    client.connect()

    stop_event = Event()
    threads = start_subscribers(mqtt_config, topics, stop_event)

    handlers = {
        "search_phrase": lambda message: search(
            client, named["database_output"], message, databases, settings),
        "add_phrase": lambda message: add_sku(message, topics, databases),
        "save_frame": lambda message: store_frame(
            client, named["frame_ack"], message, connection, settings),
        "save_result": lambda message: store_result(
            client, named["result_ack"], message, connection, settings),
    }

    try:
        while True:
            time.sleep(0.1)

            message = next_command(topics)
            if message is None:
                continue

            handler = handlers.get(message.get("command"))
            if handler is None:
                continue

            try:
                handler(message)
            except Exception as exc:
                # One bad command loses that command. Letting it out of the
                # loop would lose every command after it too.
                warning(f"Command {message.get('command')!r} failed: {exc}")

    except KeyboardInterrupt:
        info("Shutting down subscribe listener and exiting.")
    finally:
        stop_event.set()
        for thread in threads:
            if thread.is_alive():
                thread.join(timeout=2)


if __name__ == "__main__":
    main()
