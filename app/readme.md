# Application

The service entrypoint is `main.py`. It loads the broker, database, table, and
MQTT topic settings from `dependencies/config.yaml`, connects to the configured
SQLite database, and starts one subscriber thread per subscribed topic.

## Configuration

`dependencies/loadConfig.py` exposes the parsed configuration through
`get_config()` and `return_config_value(key)`. The relevant settings are:

- `broker_details.mqtt_ip` and `broker_details.mqtt_port`
- `database[].file_location` and `database[].database_name`
- `database[].tables[].churchill_sku_table`
- `database[].search_threshold`
- `topics[]`, including each topic's `is_subscribe` and `is_trigger` flags

The service checks that the configured table exists before listening. A
threshold of `0` selects exact equality; a positive threshold selects fuzzy
numeric comparisons for all supplied, non-null fields.

Start it from the repository root:

```powershell
python app/main.py
```

