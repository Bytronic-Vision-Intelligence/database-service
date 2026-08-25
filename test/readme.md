# Tests

Tests are written with pytest and cover configuration loading, MQTT listener
behavior, service shutdown, and database query construction.

Run all tests from the repository root:

```powershell
python -m pytest test
```

The tests use fakes for MQTT and service threads where appropriate, so the
suite does not require a running MQTT broker.
