# Database Service

Python MQTT service for adding, updating, removing and searching SKU records
in a local SQLite database. Searches match exact values, or values within a
configured tolerance, nearest first.

## Requirements

- Python 3.8 or newer
- An MQTT broker, normally available at `localhost:1883`

## Setup

From the repository root, create a virtual environment and install the pinned
dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

`config.example.yaml` documents every setting, in the same layout as the other
services (`project`, `service_id`, `mqtt` with its `topics`, `service`,
`logging`). Under service-orchestrator the real config is written for you to
`app/configs/config.yaml` and passed with `--config`. To run by hand, copy the
example to `config.yaml` at the repository root, set the broker, database path
and table, and run:

```powershell
python app/main.py                      # reads ./config.yaml
python app/main.py --config path\to\config.yaml
```

The configured table must already exist when the service starts.

## Search settings (`service.database`)

| Setting | Effect |
|---|---|
| neither tolerance setting, or `search_threshold: 0` | exact match on every searchable column |
| `search_threshold: n` | each column may differ by `n` percent of the measured value |
| `search_tolerances: {column: {absolute: n} \| {percent: n}}` | a tolerance per column, which wins over `search_threshold`; `absolute` is in the column's own units. Every searchable column needs an entry; a bad entry stops the service at start-up. |
| `max_results: n` | with a tolerance, return only the nearest `n` rows, and read the stored images of those rows only |

With a tolerance, results always come back nearest first: each column's
distance as a share of its tolerance, summed. The service also creates an
index on the searchable columns at start-up (`idx_<table>_search`), so a search
does not read every row's stored images.

If an instruction carries a `message_id`, the service waits for the
measurements and images with the same `message_id` and discards older ones, so
a cycle never uses data captured for an earlier instruction. Without one it
uses the next message on each topic, as before.

## MySQL

Only SQLite works. `MysqlDatabaseActions` exists but cannot be used yet: it is
missing four required methods (so it cannot be created), calls a
`_disconnect` method that does not exist, has no search queries, and nothing
in the config selects it. It will be fixed during the database-service rework.

Run the test suite with:

```powershell
python -m pytest test
```

## MQTT API

Subscribe to `[project_name]/db/search/sku_data` for commands and publish results to
`[project_name]/db/search/matching_sku`.

Search command:

```json
{
	"command": "search_phrase",
	"database_name": "[project_name]_database",
	"destination": "sku_table",
	"diameter": 100.0,
	"area": 250.0
}
```

`command`, `database_name`, and `destination` identify the request. Any other
non-null fields are used as search columns, within the tolerances described
under *Search settings*. The response is JSON keyed by row index, nearest
first, with each row mapped to its column names.

Add command:

```json
{
	"command": "add_phrase",
	"database_name": "[project_name]_database",
	"destination": "sku_table",
	"diameter": 100.0,
	"area": 250.0,
    "perimeter": 500
}
```

## Project layout

- `app/` - service entrypoint and database/MQTT dependencies
- `config.example.yaml` - the documented config layout
- `docs/` - supporting documentation and license
- `test/` - pytest tests
- `tools/` - operational helper documentation

