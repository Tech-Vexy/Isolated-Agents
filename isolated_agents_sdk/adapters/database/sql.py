"""SQL Database Adapter for the Isolated Agents SDK."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from isolated_agents_sdk.adapters.database.base import DatabaseAdapter

logger = logging.getLogger(__name__)

try:
    from sqlalchemy import create_engine, text
    from sqlalchemy.ext.asyncio import create_async_engine
    _SQLALCHEMY_AVAILABLE = True
except ImportError:
    _SQLALCHEMY_AVAILABLE = False

class SQLDatabaseAdapter(DatabaseAdapter):
    """Adapter for SQL databases using SQLAlchemy.
    
    Supports PostgreSQL, MySQL, SQLite, and more.
    """

    def __init__(self, connection_string: str, use_async: bool = False):
        self.connection_string = connection_string
        self.use_async = use_async
        self._engine = None
        
        if not _SQLALCHEMY_AVAILABLE:
            raise ImportError(
                "sqlalchemy is required for SQLDatabaseAdapter. "
                "Install it with 'pip install sqlalchemy'"
            )

    async def initialize(self) -> None:
        if self._engine:
            return
            
        if self.use_async:
            self._engine = create_async_engine(self.connection_string)
        else:
            self._engine = create_engine(self.connection_string)
        
        logger.info(f"Initialized SQL adapter for {self.connection_string}")

    async def query(self, query: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        if not self._engine:
            await self.initialize()
            
        if self.use_async:
            async with self._engine.connect() as conn:
                result = await conn.execute(text(query), params or {})
                return [dict(row._mapping) for row in result.all()]
        else:
            with self._engine.connect() as conn:
                result = conn.execute(text(query), params or {})
                return [dict(row._mapping) for row in result.all()]

    async def execute(self, command: str, params: Optional[Dict[str, Any]] = None) -> int:
        if not self._engine:
            await self.initialize()
            
        if self.use_async:
            async with self._engine.begin() as conn:
                result = await conn.execute(text(command), params or {})
                return result.rowcount
        else:
            with self._engine.begin() as conn:
                result = conn.execute(text(command), params or {})
                return result.rowcount

    async def close(self) -> None:
        if self._engine:
            if self.use_async:
                await self._engine.dispose()
            else:
                self._engine.dispose()
            self._engine = None

    def get_adapter_name(self) -> str:
        return f"SqlAlchemy:{self._engine.name if self._engine else 'uninitialized'}"
