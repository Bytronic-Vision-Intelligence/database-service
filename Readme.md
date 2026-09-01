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


## Configuration

The service takes its config from a file and will not start without one:

| Invocation | Config used |
|---|---|
| `python app/main.py --config <path>` | the supplied file — how deployment works |
| `python app/main.py --test` | `app/dependencies/config.yaml`, the bundled example |
| `python app/main.py` | none; exits with an error |

Required top-level keys are `broker_details`, `topics` and `database`. A
missing key fails at startup naming both the key and the config file, rather
than surfacing as a `KeyError` several frames down.

`database[].file_location` is repository-relative by default, so it resolves
both under the orchestrator (which runs with `cwd` set to this directory) and
from the repository root.

### Running under service-orchestrator

[service-orchestrator](https://github.com/Bytronic-Vision-Intelligence/service-orchestrator)
launches services as `app/main.py --config <path>`, with a `.venv` in each
service directory. This service satisfies that contract.

`/config.yaml` and `/config-*.yaml` are gitignored, because the orchestrator
writes them into the repository root at startup.

## Development

```bash
python -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m pytest test
```

### Running CI locally

`docker-local/` runs `.github/workflows/` on your machine through
[nektos/act](https://github.com/nektos/act). It needs Docker running.

```bash
./docker-local/run.sh -l          # list jobs
./docker-local/run.sh             # full push event
./docker-local/run.sh --fresh     # wipe the toolcache first
```

Jobs run one at a time. act shares a single `act-toolcache` volume across job
containers, so concurrent matrix legs can corrupt each other's
`/opt/hostedtoolcache` — which surfaces as `Fatal Python error: Bus error`
while loading a native module. Real GitHub gives each leg its own runner.

The `windows-latest` leg runs on a Linux image, so it proves job ordering, not
Windows behaviour. And act bind-mounts the working tree rather than doing a
fresh checkout, so anything depending on what git actually committed can pass
locally and still fail on GitHub.
