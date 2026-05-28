"""Configuration file support for Isolated Agents SDK.

This module provides support for loading agent configurations from YAML or JSON files,
making it easier to manage multiple agents and share configurations across teams.

Example YAML configuration:
    # isolated-agents.yaml
    default_policy:
      cpu_cores: 2.0
      memory_mb: 2048
      timeout_seconds: 300
      network:
        disabled: false
        allowed_endpoints:
          - api.openai.com:443
      pip_packages:
        - requests
        - pandas
      allowed_env_vars:
        - OPENAI_API_KEY
    
    agents:
      data_processor:
        workspace: ./workspace/data
        policy:
          memory_mb: 4096
          pip_packages:
            - pandas
            - numpy
            - matplotlib
      
      web_scraper:
        workspace: ./workspace/scraper
        policy:
          network:
            allowed_endpoints:
              - example.com:443

Note: Output is automatically placed in workspace/output/ for each agent.

Usage:
    >>> from isolated_agents_sdk import Agent
    >>> from isolated_agents_sdk.config import load_config
    >>> 
    >>> config = load_config("isolated-agents.yaml")
    >>> agent = Agent.from_config(config, "data_processor")
    >>> result = agent.run()
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional, Union

from isolated_agents_sdk.models import NetworkPolicy, Policy


class AgentConfig:
    """Configuration for a single agent.
    
    Attributes:
        name: Agent name
        workspace: Workspace directory path (output will be workspace/output)
        policy: Policy configuration
        description: Optional description
    """
    
    def __init__(
        self,
        name: str,
        workspace: Union[str, Path],
        policy: Optional[Dict[str, Any]] = None,
        description: Optional[str] = None,
    ):
        self.name = name
        self.workspace = Path(workspace)
        self.policy_dict = policy or {}
        self.description = description
    
    def build_policy(self, default_policy: Optional[Dict[str, Any]] = None) -> Policy:
        """Build Policy object from configuration.
        
        Args:
            default_policy: Default policy to merge with agent-specific policy
        
        Returns:
            Policy object
        """
        # Start with default policy
        merged = default_policy.copy() if default_policy else {}
        
        # Merge agent-specific policy
        merged = _deep_merge(merged, self.policy_dict)
        
        # Handle network policy specially
        if "network" in merged:
            network_dict = merged["network"]
            merged["network"] = NetworkPolicy(**network_dict)
        
        return Policy(**merged)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "workspace": str(self.workspace),
            "policy": self.policy_dict,
            "description": self.description,
        }


class Config:
    """Main configuration object.
    
    Attributes:
        default_policy: Default policy applied to all agents
        agents: Dictionary of agent configurations
        metadata: Optional metadata (version, author, etc.)
    """
    
    def __init__(
        self,
        default_policy: Optional[Dict[str, Any]] = None,
        agents: Optional[Dict[str, AgentConfig]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        self.default_policy = default_policy or {}
        self.agents = agents or {}
        self.metadata = metadata or {}
    
    def get_agent(self, name: str) -> AgentConfig:
        """Get agent configuration by name.
        
        Args:
            name: Agent name
        
        Returns:
            AgentConfig object
        
        Raises:
            KeyError: If agent not found
        """
        if name not in self.agents:
            available = ", ".join(self.agents.keys())
            raise KeyError(
                f"Agent '{name}' not found in configuration. "
                f"Available agents: {available}"
            )
        return self.agents[name]
    
    def list_agents(self) -> list[str]:
        """List all agent names."""
        return list(self.agents.keys())
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "default_policy": self.default_policy,
            "agents": {
                name: agent.to_dict()
                for name, agent in self.agents.items()
            },
            "metadata": self.metadata,
        }


def load_config(path: Union[str, Path]) -> Config:
    """Load configuration from YAML or JSON file.
    
    Args:
        path: Path to configuration file (.yaml, .yml, or .json)
    
    Returns:
        Config object
    
    Raises:
        FileNotFoundError: If file doesn't exist
        ValueError: If file format is not supported
    
    Example:
        >>> config = load_config("isolated-agents.yaml")
        >>> print(config.list_agents())
        ['data_processor', 'web_scraper']
    """
    path = Path(path)
    
    if not path.exists():
        raise FileNotFoundError(f"Configuration file not found: {path}")
    
    # Load file based on extension
    if path.suffix in [".yaml", ".yml"]:
        data = _load_yaml(path)
    elif path.suffix == ".json":
        data = _load_json(path)
    else:
        raise ValueError(
            f"Unsupported file format: {path.suffix}. "
            f"Use .yaml, .yml, or .json"
        )
    
    return _parse_config(data)


def save_config(config: Config, path: Union[str, Path]) -> None:
    """Save configuration to YAML or JSON file.
    
    Args:
        config: Config object to save
        path: Path to save to (.yaml, .yml, or .json)
    
    Example:
        >>> config = Config(default_policy={"memory_mb": 2048})
        >>> save_config(config, "isolated-agents.yaml")
    """
    path = Path(path)
    data = config.to_dict()
    
    if path.suffix in [".yaml", ".yml"]:
        _save_yaml(data, path)
    elif path.suffix == ".json":
        _save_json(data, path)
    else:
        raise ValueError(
            f"Unsupported file format: {path.suffix}. "
            f"Use .yaml, .yml, or .json"
        )


def _parse_config(data: Dict[str, Any]) -> Config:
    """Parse configuration dictionary into Config object."""
    default_policy = data.get("default_policy", {})
    metadata = data.get("metadata", {})
    
    agents = {}
    for name, agent_data in data.get("agents", {}).items():
        agents[name] = AgentConfig(
            name=name,
            workspace=agent_data.get("workspace", "./workspace"),
            policy=agent_data.get("policy", {}),
            description=agent_data.get("description"),
        )
    
    return Config(
        default_policy=default_policy,
        agents=agents,
        metadata=metadata,
    )


def _load_yaml(path: Path) -> Dict[str, Any]:
    """Load YAML file."""
    try:
        import yaml
    except ImportError:
        raise ImportError(
            "PyYAML is required to load YAML configuration files. "
            "Install it with: pip install pyyaml"
        )
    
    with open(path, 'r') as f:
        return yaml.safe_load(f) or {}


def _save_yaml(data: Dict[str, Any], path: Path) -> None:
    """Save YAML file."""
    try:
        import yaml
    except ImportError:
        raise ImportError(
            "PyYAML is required to save YAML configuration files. "
            "Install it with: pip install pyyaml"
        )
    
    with open(path, 'w') as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)


def _load_json(path: Path) -> Dict[str, Any]:
    """Load JSON file."""
    with open(path, 'r') as f:
        return json.load(f)


def _save_json(data: Dict[str, Any], path: Path) -> None:
    """Save JSON file."""
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """Deep merge two dictionaries.
    
    Args:
        base: Base dictionary
        override: Dictionary to merge in (takes precedence)
    
    Returns:
        Merged dictionary
    """
    result = base.copy()
    
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    
    return result


def create_default_config(path: Union[str, Path]) -> None:
    """Create a default configuration file.
    
    Args:
        path: Path to create configuration file
    
    Example:
        >>> create_default_config("isolated-agents.yaml")
    """
    default_config = Config(
        default_policy={
            "cpu_cores": 2.0,
            "memory_mb": 2048,
            "timeout_seconds": 300,
            "network": {
                "disabled": False,
                "allowed_endpoints": [
                    "api.openai.com:443",
                    "api.anthropic.com:443",
                ]
            },
            "pip_packages": [
                "requests",
            ],
            "allowed_env_vars": [
                "OPENAI_API_KEY",
                "ANTHROPIC_API_KEY",
            ],
        },
        agents={
            "example_agent": AgentConfig(
                name="example_agent",
                workspace="./workspace",
                policy={
                    "pip_packages": ["pandas", "numpy"],
                },
                description="Example agent configuration",
            ),
        },
        metadata={
            "version": "1.0",
            "description": "Isolated Agents SDK configuration",
        },
    )
    
    save_config(default_config, path)
    print(f"Created default configuration at: {path}")
