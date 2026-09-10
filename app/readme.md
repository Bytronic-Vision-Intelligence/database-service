# app

`main.py` is the entrypoint. It runs the configuration it is given, connects to
the broker, opens every configured SQLite database, and answers the commands
that arrive on its trigger topics.

```bash
python app/main.py --config /path/to/config.yaml
```

`--config` is required and there is no fallback. A service that found a config
beside itself would start whenever one happened to be there — a stale copy, or
another instance's file — and look healthy while being the wrong service.

## The commands

Each arrives as a JSON payload with a `command` key, on any topic marked
`is_trigger`.

| `command` | What happens | Where |
|---|---|---|
| `search_phrase` | fuzzy-search a table, publish matches to `database_output` | `search` |
| `add_phrase` | add a row, with whatever the image feeds currently show | `add_sku` |
| `save_frame` | write a frame to the image store, acknowledge on `frame_ack` | `store_frame` |
| `save_result` | record an inference result, acknowledge on `result_ack` | `store_result` |

An unrecognised `command` is ignored. A handler that raises loses that one
command, not the service.

## The functions

| | |
|---|---|
| `require`, `start_subscribers` | byte-identical to `service-template`; a test pins them |
| `topic_named` | finds a topic by its `name:`, and exits when there isn't one |
| `read` | the next payload on one topic, blocking only if given a timeout |
| `next_command` | the next command waiting on any trigger topic |
| `collect_images` | attach the latest frame from each image feed to an add |
| `open_databases` | open every configured database, keyed by name |
| `search`, `add_sku`, `store_frame`, `store_result` | one per command |
| `publish` | send one message, losing it rather than the service |

Topics are found **by name**, never by position. The search output used to be
`next(t for t in topics if not t["is_subscribe"])` — the first unsubscribed
entry, of which there are three, so reordering the config would have sent
matches to an acknowledgement topic.

## Configuration

| Key | Meaning |
|---|---|
| `mqtt.mqtt_ip`, `mqtt.mqtt_port` | the broker |
| `mqtt.topics` | looked up by name; every name in `REQUIRED_TOPICS` must be present |
| `service.databases` | one entry per database: name, file, `sku_table`, `search_threshold` |
| `service.image_store` | where captured frames are written; only the path goes in the database |
| `service.frames_table`, `service.results_table` | this service's own bookkeeping, created if absent |
| `logging.level` | how much this service says |

`config.example.yaml` in the repository root is the documented shape. The real
file is written by service-orchestrator and passed with `--config`.

## Known: `SqliteDatabaseActions.create_table` does not work

Its own docstring says so. It tries to parameterise a table name
(`CREATE TABLE ?`, which SQLite does not allow), calls `list.append()` with two
arguments, and raises `self.connection` — a `Connection`, not an exception.
Nothing calls it; `frame_store.py` and `result_store.py` write their own DDL and
say why. Repairing or removing it is a separate chore.
