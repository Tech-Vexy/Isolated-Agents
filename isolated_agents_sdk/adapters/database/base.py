"""Base class for Database Adapters in the Isolated Agents SDK."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Union

class DatabaseAdapter(ABC):
    """Abstract base class for all database adapters.
    
    Database adapters allow the host to provide mediated access to databases
    for isolated agents without exposing the database network or credentials
    to the container.
    """

    @abstractmethod
    async def initialize(self) -> None:
        """Initialize the database connection."""
        pass

    @abstractmethod
    async def query(self, query: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Execute a query and return results as a list of dictionaries."""
        pass

    @abstractmethod
    async def execute(self, command: str, params: Optional[Dict[str, Any]] = None) -> int:
        """Execute a command (INSERT, UPDATE, DELETE) and return affected row count."""
        pass

    @abstractmethod
    async def close(self) -> None:
        """Close the database connection."""
        pass

    @abstractmethod
    def get_adapter_name(self) -> str:
        """Return the name of the adapter."""
        pass
