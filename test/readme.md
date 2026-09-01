# Tests

Pytest, covering configuration loading, the MQTT subscriber helpers, the main
loop's trigger handling, and SQLite query construction. No broker and no
server are required — `fakes.py` supplies the stand-ins.

```bash
.venv/bin/python -m pytest test
```

`pytest.ini` sets `pythonpath = . app`: `app` so tests import the way the
runtime does (`from main import ...`, `from dependencies... import ...`), and
`.` so the existing `app.dependencies....` style keeps working.

`conftest.py` holds one autouse fixture pinning `sys.argv` to `--test`.
Without it every config call would raise `SystemExit`, because `loadConfig`
reads `sys.argv` and would otherwise find pytest's own arguments.

Name test files `test_*.py`, lowercase. Pytest's default pattern will not
collect `Test_*.py` on a case-sensitive filesystem — this repo previously
tracked `Test_dummy.py` and `Test_mqtt_functions.py` while the working tree
held lowercase names, which macOS hid and a Linux runner would not have.
