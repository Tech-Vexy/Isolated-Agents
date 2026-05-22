"""Composite audit adapter for multiple logging backends."""

from __future__ import annotations

import asyncio
from typing import Optional

from isolated_agents_sdk.adapters.audit.base import AuditAdapter
from isolated_agents_sdk.adapters.audit.types import (
    AuditEvent,
    AuditQuery,
    EventType,
)

class CompositeAuditAdapter(AuditAdapter):
    """Audit adapter that broadcasts events to multiple other adapters.
    
    This allows simultaneous logging to persistent storage (e.g. file, DB)
    and real-time reporting (e.g. terminal telemetry, Datadog).
    """
    
    def __init__(self, adapters: list[AuditAdapter]):
        super().__init__()
        self._adapters = adapters
        self._initialized = False

    async def initialize(self) -> None:
        if self._initialized:
            return
        
        # Initialize all sub-adapters
        tasks = [adapter.initialize() for adapter in self._adapters]
        if tasks:
            await asyncio.gather(*tasks)
        self._initialized = True

    async def cleanup(self) -> None:
        if not self._initialized:
            return
            
        tasks = [adapter.cleanup() for adapter in self._adapters]
        if tasks:
            await asyncio.gather(*tasks)
        self._initialized = False

    async def log_event(
        self,
        event_type: EventType,
        session_id: str,
        agent_id: str,
        payload: Optional[dict] = None,
        user_id: Optional[str] = None,
        severity: str = "info",
        tags: Optional[dict[str, str]] = None,
    ) -> str:
        # We fire and forget or gather. Logging should generally not block excessively.
        # Returning the event ID from the first adapter that provides one.
        main_event_id = ""
        
        for i, adapter in enumerate(self._adapters):
            try:
                event_id = await adapter.log_event(
                    event_type=event_type,
                    session_id=session_id,
                    agent_id=agent_id,
                    payload=payload,
                    user_id=user_id,
                    severity=severity,
                    tags=tags
                )
                if i == 0:
                    main_event_id = event_id
            except Exception:
                # We don't want one failing adapter to kill the whole logging process
                pass
                
        return main_event_id

    async def query_events(self, query: AuditQuery) -> list[AuditEvent]:
        # Query from the first adapter that supports it (usually the persistent one)
        for adapter in self._adapters:
            try:
                return await adapter.query_events(query)
            except (NotImplementedError, AttributeError):
                continue
        return []

    async def get_event(self, event_id: str) -> AuditEvent:
        for adapter in self._adapters:
            try:
                return await adapter.get_event(event_id)
            except (NotImplementedError, AttributeError):
                continue
        raise NotImplementedError("None of the adapters support event retrieval")

    async def health_check(self) -> bool:
        # Healthy if all sub-adapters are healthy
        results = await asyncio.gather(*[adapter.health_check() for adapter in self._adapters])
        return all(results)
