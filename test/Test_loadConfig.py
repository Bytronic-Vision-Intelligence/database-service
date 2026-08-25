import pytest
import sys
import pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from app.dependencies.loadConfig import return_config_value, get_config

def test_return_config_value():
    # Test that the function returns the correct value for a given key
    config = get_config()
    assert return_config_value("broker_details") == config.get("broker_details")

    with pytest.raises(KeyError):
        return_config_value("non_existent_key")

    with pytest.raises(ValueError):
        return_config_value("")

def main():
    test_return_config_value()

if __name__ == "__main__":
    pytest.main()