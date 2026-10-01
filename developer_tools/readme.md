# Developer tools

Operational scripts and database utilities.
Run from the repository root so imports and paths resolve consistently.

Create the tables listed in the orchestrator config, and add any configured
columns that an existing table does not have yet. The running service does
not create tables or add columns:

```powershell
python developer_tools/create_tables.py --config ../configs/config.yaml
```

The service itself is started with:

```powershell
python app/main.py
```

For setup and MQTT payload examples, see the repository [README](../Readme.md).
