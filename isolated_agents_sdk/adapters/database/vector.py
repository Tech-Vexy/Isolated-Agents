"""Vector Database Adapter for the Isolated Agents SDK."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Union

from isolated_agents_sdk.adapters.database.base import DatabaseAdapter

logger = logging.getLogger(__name__)

class VectorDatabaseAdapter(DatabaseAdapter):
    """Adapter for Vector databases (Chroma, Pinecone)."""

    def __init__(self, db_type: str, **kwargs):
        self.db_type = db_type.lower()
        self.kwargs = kwargs
        self._client = None
        self._collection = None

    async def initialize(self) -> None:
        if self._client:
            return

        if self.db_type == "chroma":
            try:
                import chromadb
                path = self.kwargs.get("path", "./chroma_db")
                self._client = chromadb.PersistentClient(path=path)
            except ImportError:
                raise ImportError("chromadb is required for Chroma support. Install it with 'pip install chromadb'")
        
        elif self.db_type == "pinecone":
            try:
                from pinecone import Pinecone
                api_key = self.kwargs.get("api_key")
                self._client = Pinecone(api_key=api_key)
            except ImportError:
                raise ImportError("pinecone-client is required for Pinecone support. Install it with 'pip install pinecone-client'")
        
        else:
            raise ValueError(f"Unsupported Vector DB type: {self.db_type}")

    async def query(self, query: Any, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Perform a similarity search."""
        if not self._client:
            await self.initialize()

        collection_name = params.get("collection") if params else "default"
        top_k = params.get("top_k", 5) if params else 5

        if self.db_type == "chroma":
            collection = self._client.get_or_create_collection(name=collection_name)
            # query can be a list of embeddings or text strings
            results = collection.query(
                query_embeddings=query if isinstance(query[0], (float, int)) else None,
                query_texts=query if isinstance(query, str) or (isinstance(query, list) and isinstance(query[0], str)) else None,
                n_results=top_k
            )
            
            # Format results
            flattened = []
            if results["ids"]:
                for i in range(len(results["ids"][0])):
                    flattened.append({
                        "id": results["ids"][0][i],
                        "document": results["documents"][0][i] if results["documents"] else None,
                        "metadata": results["metadatas"][0][i] if results["metadatas"] else None,
                        "distance": results["distances"][0][i] if results["distances"] else None
                    })
            return flattened

        elif self.db_type == "pinecone":
            index = self._client.Index(collection_name)
            results = index.query(
                vector=query,
                top_k=top_k,
                include_metadata=True
            )
            return [
                {
                    "id": match.id,
                    "score": match.score,
                    "metadata": match.metadata
                } for match in results.matches
            ]

        return []

    async def execute(self, command: str, params: Optional[Dict[str, Any]] = None) -> int:
        """Upsert or delete vectors."""
        if not self._client:
            await self.initialize()

        collection_name = params.get("collection") if params else "default"

        if self.db_type == "chroma":
            collection = self._client.get_or_create_collection(name=collection_name)
            if command == "upsert":
                collection.upsert(
                    ids=params.get("ids", []),
                    embeddings=params.get("embeddings"),
                    metadatas=params.get("metadatas"),
                    documents=params.get("documents")
                )
                return len(params.get("ids", []))
            elif command == "delete":
                collection.delete(ids=params.get("ids", []))
                return len(params.get("ids", []))

        elif self.db_type == "pinecone":
            index = self._client.Index(collection_name)
            if command == "upsert":
                vectors = params.get("vectors", [])
                result = index.upsert(vectors=vectors)
                return result.upserted_count
            elif command == "delete":
                index.delete(ids=params.get("ids", []))
                return len(params.get("ids", []))

        return 0

    async def close(self) -> None:
        # Most vector clients don't need explicit closing or have different mechanisms
        self._client = None

    def get_adapter_name(self) -> str:
        return f"VectorDB:{self.db_type}"
