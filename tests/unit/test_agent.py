from pathlib import Path

import pytest

from isolated_agents_sdk.agent import Agent, agent
from isolated_agents_sdk.config import AgentConfig, Config
from isolated_agents_sdk.models import Policy


def dummy_agent_func():
    return "success"

def test_agent_initialization():
    my_agent = Agent(dummy_agent_func, workspace="/test/workspace")
    assert my_agent.func == dummy_agent_func
    assert my_agent._workspace == Path("/test/workspace")
    assert my_agent._memory_mb == 512  # Default

def test_agent_fluent_api():
    my_agent = (Agent(dummy_agent_func)
                .with_workspace("/custom/workspace")
                .with_memory(2048)
                .with_cpu(2.0)
                .with_timeout(60)
                .with_network(enabled=True, allowed=["api.example.com"])
                .with_packages("requests")
                .with_env("API_KEY", DEBUG="1"))

    assert my_agent._workspace == Path("/custom/workspace")

    policy = my_agent._build_policy()
    assert policy.memory_mb == 2048
    assert policy.cpu_cores == 2.0
    assert policy.timeout_seconds == 60
    assert policy.network.disabled is False
    assert "api.example.com" in policy.network.allowed_endpoints
    assert "requests" in policy.pip_packages
    assert "API_KEY" in policy.allowed_env_vars
    assert policy.env_vars["DEBUG"] == "1"

def test_agent_decorator():
    @agent(workspace="/decorated/workspace", memory=1024, network=True)
    def decorated_agent():
        pass

    assert isinstance(decorated_agent, Agent)
    assert decorated_agent._workspace == Path("/decorated/workspace")

    policy = decorated_agent._build_policy()
    assert policy.memory_mb == 1024
    assert policy.network.disabled is False

def test_agent_from_config():
    cfg = Config(
        default_policy={"timeout_seconds": 120},
        agents={
            "my_agent": AgentConfig(
                name="my_agent",
                workspace="/config/workspace",
                policy={"memory_mb": 4096}
            )
        }
    )

    my_agent = Agent.from_config(cfg, "my_agent", dummy_agent_func)

    assert my_agent._workspace == Path("/config/workspace")
    policy = my_agent._build_policy()
    assert policy.memory_mb == 4096
    assert policy.timeout_seconds == 120

def test_agent_run_raises_without_workspace():
    my_agent = Agent(dummy_agent_func)
    with pytest.raises(ValueError, match="Workspace path must be set"):
        my_agent.run()
