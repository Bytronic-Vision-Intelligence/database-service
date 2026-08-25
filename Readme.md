# Database Service

Python MQTT service for adding and searching SKU records in a local
SQLite database. Searches use exact matching when the threshold is `0` and
numeric fuzzy matching when the configured threshold is greater than `0`.

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

Update `app/dependencies/config.yaml` with the broker, SQLite database path,
table name, and fuzzy-search threshold. The configured table must already
exist when the service starts.

Run the service with:

```powershell
python app/main.py
```

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
non-null fields are used as search columns. With the default threshold of `20`,
each numeric value may differ by up to `20` from the stored value. The response
is JSON keyed by row index, with each row mapped to its column names.

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
- `database/` - SQLite database files
- `docs/` - supporting documentation and license
- `test/` - pytest tests
- `tools/` - operational helper documentation

