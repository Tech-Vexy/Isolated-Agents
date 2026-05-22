"""NoSQL Database Adapter for the Isolated Agents SDK."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Union

from isolated_agents_sdk.adapters.database.base import DatabaseAdapter

logger = logging.getLogger(__name__)

class NoSQLDatabaseAdapter(DatabaseAdapter):
    """Adapter for NoSQL databases (MongoDB, Redis)."""

    def __init__(self, db_type: str, connection_string: str, **kwargs):
        self.db_type = db_type.lower()
        self.connection_string = connection_string
        self.kwargs = kwargs
        self._client = None
        self._db = None

    async def initialize(self) -> None:
        if self._client:
            return

        if self.db_type == "mongodb":
            try:
                import motor.motor_asyncio
                self._client = motor.motor_asyncio.AsyncIOMotorClient(self.connection_string)
                db_name = self.kwargs.get("database", "default")
                self._db = self._client[db_name]
            except ImportError:
                raise ImportError("motor is required for MongoDB support. Install it with 'pip install motor'")
        
        elif self.db_type == "redis":
            try:
                import redis.asyncio as redis
                self._client = redis.from_url(self.connection_string, decode_responses=True)
            except ImportError:
                raise ImportError("redis is required for Redis support. Install it with 'pip install redis'")
        
        else:
            raise ValueError(f"Unsupported NoSQL type: {self.db_type}")

    async def query(self, query: Union[str, Dict[str, Any]], params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        if not self._client:
            await self.initialize()

        if self.db_type == "mongodb":
            collection_name = params.get("collection") if params else None
            if not collection_name:
                raise ValueError("MongoDB query requires 'collection' in params")
            
            # query is a JSON filter for MongoDB
            filter_dict = query if isinstance(query, dict) else {}
            cursor = self._db[collection_name].find(filter_dict)
            results = []
            async for doc in cursor:
                # Convert ObjectId to string for JSON serialization
                if "_id" in doc:
                    doc["_id"] = str(doc["_id"])
                results.append(doc)
            return results

        elif self.db_type == "redis":
            # For Redis, we treat 'query' as a key or a pattern
            if "*" in str(query):
                keys = await self._client.keys(query)
                results = []
                for k in keys:
                    val = await self._client.get(k)
                    results.append({"key": k, "value": val})
                return results
            else:
                val = await self._client.get(query)
                return [{"key": query, "value": val}]

        return []

    async def execute(self, command: str, params: Optional[Dict[str, Any]] = None) -> int:
        if not self._client:
            await self.initialize()

        if self.db_type == "mongodb":
            collection_name = params.get("collection") if params else None
            if not collection_name:
                raise ValueError("MongoDB execute requires 'collection' in params")
            
            # command is a command name, params contains data
            if command == "insert":
                result = await self._db[collection_name].insert_one(params.get("document", {}))
                return 1 if result.acknowledged else 0
            elif command == "update":
                result = await self._db[collection_name].update_many(
                    params.get("filter", {}), 
                    {"$set": params.get("update", {})}
                )
                return result.modified_count
            elif command == "delete":
                result = await self._db[collection_name].delete_many(params.get("filter", {}))
                return result.deleted_count

        elif self.db_type == "redis":
            if command == "set":
                await self._client.set(params.get("key"), params.get("value"))
                return 1
            elif command == "delete":
                return await self._client.delete(params.get("key"))

        return 0

    async def close(self) -> None:
        if self._client:
            if self.db_type == "mongodb":
                self._client.close()
            elif self.db_type == "redis":
                await self._client.close()
            self._client = None

    def get_adapter_name(self) -> str:
        return f"NoSQL:{self.db_type}"
