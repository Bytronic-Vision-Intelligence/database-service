"""loadConfig reads whatever `app/configs/config.yaml` the orchestrator wrote.

The test used to assert against that real file, so it passed only on a machine
where sync_configs.py had already run and failed everywhere else -- it was
testing the deployment, not the loader. Each case now writes its own config and
points the loader at it.
"""

import pytest

from app.dependencies import loadConfig
from app.dependencies.loadConfig import get_config, return_config_value


@pytest.fixture
def config_file(tmp_path, monkeypatch):
    """Redirect the loader at a config this test owns."""
    path = tmp_path / "config.yaml"

    def write(text: str) -> None:
        path.write_text(text, encoding="utf-8")

    monkeypatch.setattr(loadConfig, "_config_path", lambda: path)
    return write


def test_return_config_value_reads_the_key(config_file):
    config_file("broker_details:\n  mqtt_ip: localhost\n  mqtt_port: 1883\n")

    assert return_config_value("broker_details") == {
        "mqtt_ip": "localhost",
        "mqtt_port": 1883,
    }
    assert return_config_value("broker_details") == get_config()["broker_details"]


def test_missing_key_raises_key_error(config_file):
    config_file("broker_details:\n  mqtt_ip: localhost\n")

    with pytest.raises(KeyError):
        return_config_value("non_existent_key")


def test_empty_key_raises_value_error(config_file):
    config_file("broker_details:\n  mqtt_ip: localhost\n")

    with pytest.raises(ValueError):
        return_config_value("")


def test_absent_config_file_is_an_empty_config(tmp_path, monkeypatch):
    """A service starting before sync_configs.py has run must not crash here."""
    monkeypatch.setattr(
        loadConfig, "_config_path", lambda: tmp_path / "does-not-exist.yaml"
    )

    assert get_config() == {}
    with pytest.raises(KeyError):
        return_config_value("broker_details")
