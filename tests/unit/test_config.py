import json
from pathlib import Path
from typing import Any, Dict

import pytest

from isolated_agents_sdk.config import (
    AgentConfig,
    Config,
    create_default_config,
    load_config,
    save_config,
)


@pytest.fixture
def temp_workspace(tmp_path: Path) -> Path:
    return tmp_path

def test_create_and_load_default_yaml_config(temp_workspace: Path):
    config_file = temp_workspace / "default.yaml"
    create_default_config(config_file)

    assert config_file.exists()

    config = load_config(config_file)
    assert config.metadata["version"] == "1.0"
    assert "example_agent" in config.list_agents()

    agent_cfg = config.get_agent("example_agent")
    assert agent_cfg.name == "example_agent"

def test_save_and_load_toml_config(temp_workspace: Path):
    config_file = temp_workspace / "test_config.toml"

    original_config = Config(
        default_policy={"memory_mb": 1024},
        agents={
            "toml_agent": AgentConfig(
                name="toml_agent",
                workspace="./toml_workspace",
                policy={"cpu_cores": 4.0}
            )
        }
    )

    save_config(original_config, config_file)
    assert config_file.exists()

    loaded_config = load_config(config_file)
    assert loaded_config.default_policy["memory_mb"] == 1024

    agent_cfg = loaded_config.get_agent("toml_agent")
    assert agent_cfg.workspace == Path("./toml_workspace")
    assert agent_cfg.policy_dict["cpu_cores"] == 4.0

def test_save_and_load_json_config(temp_workspace: Path):
    config_file = temp_workspace / "test_config.json"

    original_config = Config(
        default_policy={"timeout_seconds": 60}
    )

    save_config(original_config, config_file)
    assert config_file.exists()

    loaded_config = load_config(config_file)
    assert loaded_config.default_policy["timeout_seconds"] == 60

def test_load_config_unsupported_format(temp_workspace: Path):
    config_file = temp_workspace / "test_config.ini"
    config_file.touch()

    with pytest.raises(ValueError, match="Unsupported file format"):
        load_config(config_file)

def test_save_config_unsupported_format(temp_workspace: Path):
    config_file = temp_workspace / "test_config.ini"
    config = Config()

    with pytest.raises(ValueError, match="Unsupported file format"):
        save_config(config, config_file)
