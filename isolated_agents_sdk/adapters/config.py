"""Configuration system for adapter selection and management.

This module provides a flexible configuration system that allows users to:
- Configure adapters through Python dictionaries
- Load adapter configuration from YAML/JSON files
- Override adapter configuration with environment variables
- Validate adapter configuration before initialization
- Provide sensible defaults for all adapters

Example:
    >>> from isolated_agents_sdk.adapters.config import AdapterConfig
    >>> 
    >>> # Create configuration with defaults
    >>> config = AdapterConfig()
    >>> 
    >>> # Override specific adapters
    >>> config = AdapterConfig(
    ...     container_adapter="podman",
    ...     storage_adapter="local",
    ...     storage_config={"base_path": "/custom/path"}
    ... )
    >>> 
    >>> # Load from file
    >>> config = AdapterConfig.from_file("adapters.yaml")
    >>> 
    >>> # Load from environment
    >>> config = AdapterConfig.from_env()
"""

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional

try:
    import yaml  # type: ignore
    YAML_AVAILABLE = True
except ImportError:
    yaml = None  # type: ignore
    YAML_AVAILABLE = False


@dataclass
class AdapterConfig:
    """Configuration for all adapter types.
    
    This class provides a centralized configuration system for all adapters
    in the SDK. It supports multiple configuration sources and validation.
    
    Attributes:
        container_adapter: Name of the container runtime adapter to use
        container_config: Configuration dictionary for the container adapter
        storage_adapter: Name of the storage backend adapter to use
        storage_config: Configuration dictionary for the storage adapter
        audit_adapter: Name of the audit logger adapter to use
        audit_config: Configuration dictionary for the audit adapter
        policy_adapter: Name of the policy validator adapter to use
        policy_config: Configuration dictionary for the policy adapter
    """
    
    # Container adapter configuration
    container_adapter: str = "podman"
    container_config: Dict[str, Any] = field(default_factory=dict)
    
    # Storage adapter configuration
    storage_adapter: str = "local"
    storage_config: Dict[str, Any] = field(default_factory=dict)
    
    # Audit adapter configuration
    audit_adapter: str = "file"
    audit_config: Dict[str, Any] = field(default_factory=dict)
    
    # Policy adapter configuration
    policy_adapter: str = "default"
    policy_config: Dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> "AdapterConfig":
        """Create configuration from a dictionary.
        
        Args:
            config_dict: Dictionary containing adapter configuration
            
        Returns:
            AdapterConfig instance
            
        Example:
            >>> config = AdapterConfig.from_dict({
            ...     "container_adapter": "podman",
            ...     "storage_adapter": "local",
            ...     "storage_config": {"base_path": "/data"}
            ... })
        """
        return cls(
            container_adapter=config_dict.get("container_adapter", "podman"),
            container_config=config_dict.get("container_config", {}),
            storage_adapter=config_dict.get("storage_adapter", "local"),
            storage_config=config_dict.get("storage_config", {}),
            audit_adapter=config_dict.get("audit_adapter", "file"),
            audit_config=config_dict.get("audit_config", {}),
            policy_adapter=config_dict.get("policy_adapter", "default"),
            policy_config=config_dict.get("policy_config", {}),
        )
    
    @classmethod
    def from_file(cls, file_path: str) -> "AdapterConfig":
        """Load configuration from a YAML or JSON file.
        
        Args:
            file_path: Path to the configuration file
            
        Returns:
            AdapterConfig instance
            
        Raises:
            FileNotFoundError: If the configuration file doesn't exist
            ValueError: If the file format is not supported
            
        Example:
            >>> config = AdapterConfig.from_file("adapters.yaml")
        """
        path = Path(file_path)
        
        if not path.exists():
            raise FileNotFoundError(f"Configuration file not found: {file_path}")
        
        content = path.read_text()
        
        if path.suffix in [".yaml", ".yml"]:
            if not YAML_AVAILABLE or yaml is None:
                raise ImportError(
                    "PyYAML is required to load YAML configuration files. "
                    "Install it with: pip install pyyaml"
                )
            config_dict = yaml.safe_load(content)
        elif path.suffix == ".json":
            config_dict = json.loads(content)
        else:
            raise ValueError(
                f"Unsupported configuration file format: {path.suffix}. "
                "Supported formats: .yaml, .yml, .json"
            )
        
        return cls.from_dict(config_dict)
    
    @classmethod
    def from_env(cls, prefix: str = "ISOLATED_AGENTS") -> "AdapterConfig":
        """Load configuration from environment variables.
        
        Environment variables should be prefixed with the specified prefix
        and use the format: {PREFIX}_{ADAPTER_TYPE}_{SETTING}
        
        Args:
            prefix: Prefix for environment variables (default: "ISOLATED_AGENTS")
            
        Returns:
            AdapterConfig instance
            
        Example:
            >>> # Set environment variables:
            >>> # ISOLATED_AGENTS_CONTAINER_ADAPTER=podman
            >>> # ISOLATED_AGENTS_STORAGE_ADAPTER=local
            >>> # ISOLATED_AGENTS_STORAGE_BASE_PATH=/data
            >>> config = AdapterConfig.from_env()
        """
        def get_env(key: str, default: Any = None) -> Any:
            """Get environment variable with prefix."""
            return os.environ.get(f"{prefix}_{key}", default)
        
        def get_config_dict(adapter_type: str) -> Dict[str, Any]:
            """Extract configuration dictionary for an adapter type."""
            config = {}
            prefix_key = f"{prefix}_{adapter_type.upper()}_"
            
            for key, value in os.environ.items():
                if key.startswith(prefix_key):
                    config_key = key[len(prefix_key):].lower()
                    # Try to parse as JSON for complex values
                    try:
                        config[config_key] = json.loads(value)
                    except (json.JSONDecodeError, ValueError):
                        config[config_key] = value
            
            return config
        
        return cls(
            container_adapter=get_env("CONTAINER_ADAPTER", "podman"),
            container_config=get_config_dict("CONTAINER"),
            storage_adapter=get_env("STORAGE_ADAPTER", "local"),
            storage_config=get_config_dict("STORAGE"),
            audit_adapter=get_env("AUDIT_ADAPTER", "file"),
            audit_config=get_config_dict("AUDIT"),
            policy_adapter=get_env("POLICY_ADAPTER", "default"),
            policy_config=get_config_dict("POLICY"),
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to a dictionary.
        
        Returns:
            Dictionary representation of the configuration
            
        Example:
            >>> config = AdapterConfig()
            >>> config_dict = config.to_dict()
        """
        return {
            "container_adapter": self.container_adapter,
            "container_config": self.container_config,
            "storage_adapter": self.storage_adapter,
            "storage_config": self.storage_config,
            "audit_adapter": self.audit_adapter,
            "audit_config": self.audit_config,
            "policy_adapter": self.policy_adapter,
            "policy_config": self.policy_config,
        }
    
    def to_file(self, file_path: str, format: Optional[str] = None) -> None:
        """Save configuration to a file.
        
        Args:
            file_path: Path to save the configuration file
            format: File format ("yaml" or "json"). If not specified,
                   inferred from file extension
                   
        Raises:
            ValueError: If the format is not supported
            
        Example:
            >>> config = AdapterConfig()
            >>> config.to_file("adapters.yaml")
        """
        path = Path(file_path)
        config_dict = self.to_dict()
        
        if format is None:
            format = path.suffix.lstrip(".")
        
        if format in ["yaml", "yml"]:
            if not YAML_AVAILABLE or yaml is None:
                raise ImportError(
                    "PyYAML is required to save YAML configuration files. "
                    "Install it with: pip install pyyaml"
                )
            content = yaml.dump(config_dict, default_flow_style=False)
        elif format == "json":
            content = json.dumps(config_dict, indent=2)
        else:
            raise ValueError(
                f"Unsupported configuration file format: {format}. "
                "Supported formats: yaml, yml, json"
            )
        
        path.write_text(content)
    
    def validate(self) -> None:
        """Validate the configuration.
        
        Raises:
            ValueError: If the configuration is invalid
            
        Example:
            >>> config = AdapterConfig()
            >>> config.validate()  # Raises ValueError if invalid
        """
        # Validate adapter names
        valid_container_adapters = ["podman", "docker"]
        if self.container_adapter not in valid_container_adapters:
            raise ValueError(
                f"Invalid container adapter: {self.container_adapter}. "
                f"Valid options: {', '.join(valid_container_adapters)}"
            )
        
        valid_storage_adapters = ["local", "s3", "azure", "gcs"]
        if self.storage_adapter not in valid_storage_adapters:
            raise ValueError(
                f"Invalid storage adapter: {self.storage_adapter}. "
                f"Valid options: {', '.join(valid_storage_adapters)}"
            )
        
        valid_audit_adapters = ["file", "database", "cloudwatch"]
        if self.audit_adapter not in valid_audit_adapters:
            raise ValueError(
                f"Invalid audit adapter: {self.audit_adapter}. "
                f"Valid options: {', '.join(valid_audit_adapters)}"
            )
        
        valid_policy_adapters = ["default", "opa", "custom"]
        if self.policy_adapter not in valid_policy_adapters:
            raise ValueError(
                f"Invalid policy adapter: {self.policy_adapter}. "
                f"Valid options: {', '.join(valid_policy_adapters)}"
            )
        
        # Validate configuration dictionaries are dicts
        for config_name in ["container_config", "storage_config", "audit_config", "policy_config"]:
            config_value = getattr(self, config_name)
            if not isinstance(config_value, dict):
                raise ValueError(
                    f"{config_name} must be a dictionary, got {type(config_value)}"
                )
    
    def merge(self, other: "AdapterConfig") -> "AdapterConfig":
        """Merge this configuration with another, with other taking precedence.
        
        Args:
            other: Another AdapterConfig to merge with
            
        Returns:
            New AdapterConfig with merged values
            
        Example:
            >>> base_config = AdapterConfig()
            >>> override_config = AdapterConfig(storage_adapter="s3")
            >>> merged = base_config.merge(override_config)
        """
        def merge_dicts(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
            """Recursively merge two dictionaries."""
            result = base.copy()
            for key, value in override.items():
                if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                    result[key] = merge_dicts(result[key], value)
                else:
                    result[key] = value
            return result
        
        return AdapterConfig(
            container_adapter=other.container_adapter or self.container_adapter,
            container_config=merge_dicts(self.container_config, other.container_config),
            storage_adapter=other.storage_adapter or self.storage_adapter,
            storage_config=merge_dicts(self.storage_config, other.storage_config),
            audit_adapter=other.audit_adapter or self.audit_adapter,
            audit_config=merge_dicts(self.audit_config, other.audit_config),
            policy_adapter=other.policy_adapter or self.policy_adapter,
            policy_config=merge_dicts(self.policy_config, other.policy_config),
        )


def load_config(
    config_file: Optional[str] = None,
    use_env: bool = True,
    defaults: Optional[AdapterConfig] = None,
) -> AdapterConfig:
    """Load adapter configuration from multiple sources.
    
    Configuration is loaded in the following order (later sources override earlier):
    1. Default configuration
    2. Configuration file (if specified)
    3. Environment variables (if use_env is True)
    
    Args:
        config_file: Optional path to configuration file
        use_env: Whether to load configuration from environment variables
        defaults: Optional default configuration to use as base
        
    Returns:
        Merged AdapterConfig
        
    Example:
        >>> # Load with defaults and environment overrides
        >>> config = load_config(use_env=True)
        >>> 
        >>> # Load from file with environment overrides
        >>> config = load_config(config_file="adapters.yaml", use_env=True)
        >>> 
        >>> # Load from file only
        >>> config = load_config(config_file="adapters.yaml", use_env=False)
    """
    # Start with defaults
    config = defaults or AdapterConfig()
    
    # Load from file if specified
    if config_file:
        file_config = AdapterConfig.from_file(config_file)
        config = config.merge(file_config)
    
    # Load from environment if enabled
    if use_env:
        env_config = AdapterConfig.from_env()
        config = config.merge(env_config)
    
    # Validate final configuration
    config.validate()
    
    return config

# Made with Bob
