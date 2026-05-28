"""Built-in Agent Runtime for the Isolated Agents SDK.

Provides a unified high-level interface for managing agent sessions, 
sub-agent spawning, and background orchestration.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import socket
import struct
import uuid
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, List, Optional

_SESSION_ID_RE = re.compile(r'^[0-9a-f\-]{36}$')


def _safe_session_path(base: Path, session_id: str, suffix: str) -> Path:
    """Return a path under base for session_id, raising if session_id is not a valid UUID."""
    if not _SESSION_ID_RE.match(session_id):
        raise ValueError(f"Invalid session_id format: {session_id!r}")
    base_resolved = base.resolve()
    resolved = (base_resolved / f"{session_id}{suffix}").resolve()
    try:
        resolved.relative_to(base_resolved)
    except ValueError:
        raise ValueError(f"Path traversal detected for session_id: {session_id!r}")
    return resolved

from isolated_agents_sdk.agent_runner import AgentRunner
from isolated_agents_sdk.audit_logger import AuditLogger
from isolated_agents_sdk.container_provisioner import ContainerProvisioner
from isolated_agents_sdk.models import AgentResult, Policy, SessionInfo
from isolated_agents_sdk.session_manager import SessionManager
from isolated_agents_sdk.logging import get_logger

logger = get_logger("runtime")

class _RuntimeRegistry:
    """Encapsulates the global AgentRuntime singleton to avoid bare module-level mutation."""

    def __init__(self) -> None:
        self._instance: Optional[AgentRuntime] = None
        self._lock: Optional[asyncio.Lock] = None

    def _get_lock(self) -> asyncio.Lock:
        # Lock must be created lazily inside a running event loop.
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock

    async def get_async(self, working_dir: Optional[str | Path] = None) -> AgentRuntime:
        """Get or create the singleton (async, race-safe)."""
        async with self._get_lock():
            if self._instance is None:
                self._instance = AgentRuntime(working_dir=working_dir or "./runtime_workspace")
            return self._instance

    def get_sync(self, working_dir: Optional[str | Path] = None) -> AgentRuntime:
        """Get or create the singleton (sync, best-effort for non-async callers)."""
        if self._instance is None:
            self._instance = AgentRuntime(working_dir=working_dir or "./runtime_workspace")
        return self._instance


_runtime_registry = _RuntimeRegistry()


async def get_runtime_async(working_dir: Optional[str | Path] = None) -> AgentRuntime:
    """Get or create the global AgentRuntime instance (async, thread-safe)."""
    return await _runtime_registry.get_async(working_dir)


def get_runtime(working_dir: Optional[str | Path] = None) -> AgentRuntime:
    """Get or create the global AgentRuntime instance (sync, best-effort)."""
    return _runtime_registry.get_sync(working_dir)

class AgentRuntime:
    """Unified runtime for managing isolated agents.
    
    The AgentRuntime combines orchestration, session management, and the
    Spawn Daemon into a single service. It allows agents to spawn sub-agents
    by communicating with this runtime over a Unix domain socket.
    """

    def __init__(
        self,
        working_dir: str | Path = "./runtime_workspace",
        audit_logger: Optional[AuditLogger] = None,
        runtime_id: Optional[str] = None,
        enable_audit_logs: bool = True,
    ):
        self.working_dir = Path(working_dir)
        self.runtime_id = runtime_id or str(uuid.uuid4())[:8]
        self._spawn_socket_path: Optional[str] = None
        self._spawn_server = None
        self._hitl_handler: Optional[Callable[[str, str, int], Awaitable[str]]] = None
        
        # If audit logging is disabled (e.g. for clean CLI output),
        # we pass a Null handler if we eventually implement that,
        # but for now we just allow the user to control the AuditLogger.
        self.audit_logger = audit_logger or AuditLogger(enabled=enable_audit_logs)
        
        # Durable execution state directory
        self.state_dir = self.working_dir / "state"
        self.session_manager = SessionManager(
            audit_logger=self.audit_logger,
            state_dir=self.state_dir
        )
        self.provisioner = ContainerProvisioner(
            audit_logger=self.audit_logger
        )
        
        # State
        self._is_running = False
        self._session_servers: dict[str, asyncio.Server] = {}
        self._session_sockets: dict[str, str] = {}
        self._active_jobs: dict[str, asyncio.Task] = {}
        self._job_results: dict[str, AgentResult] = {}
        self._loop_task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        """Start the background services of the runtime."""
        if self._is_running:
            return
            
        self.working_dir.mkdir(parents=True, exist_ok=True)
        # Session sockets directory
        (self.working_dir / "sockets").mkdir(exist_ok=True)
        self._is_running = True
        
        logger.info(
            "Agent Runtime started.",
            extra={"runtime_id": self.runtime_id, "workspace": str(self.working_dir)}
        )

    async def stop(self) -> None:
        """Stop all background services and cleanup."""
        self._is_running = False
        
        for server in self._session_servers.values():
            server.close()
            
        for socket_path in self._session_sockets.values():
            if os.path.exists(socket_path):
                try:
                    os.unlink(socket_path)
                except OSError:
                    pass
        
        self._session_servers.clear()
        self._session_sockets.clear()
                
        self.session_manager.destroy_all()
        logger.info(f"Agent Runtime '{self.runtime_id}' stopped.")

    async def run_agent(
        self,
        agent: Optional[Callable],
        policy: Optional[Policy] = None,
        args: tuple = (),
        kwargs: Optional[Dict[str, Any]] = None,
        agent_payload_hex: Optional[str] = None,
    ) -> AgentResult:
        """Run an agent within this runtime context.
        
        This manages the entire lifecycle through the runtime's provisioner
        and session manager.
        """
        # We need to import async_run_agent here to avoid circular dependencies
        from isolated_agents_sdk import async_run_agent

        # 1. Create a unique session ID if not provided
        import uuid
        session_id = str(uuid.uuid4())

        # 2. Create a dedicated session socket for IPC (Security fix)
        # This prevents session spoofing because each container has its own 
        # socket that only knows about its own session_id.
        socket_path = await self._create_session_socket(session_id)
        
        try:
            return await async_run_agent(
                agent=agent,
                working_dir=self.working_dir,
                policy=policy,
                agent_args=args,
                agent_kwargs=kwargs,
                agent_payload_hex=agent_payload_hex,
                spawn_socket_path=socket_path, # Dedicated socket
                audit_logger=self.audit_logger,
                session_id=session_id # Pass the pre-generated session ID
            )
        finally:
            await self._close_session_socket(session_id)

    async def _create_session_socket(self, session_id: str) -> Optional[str]:
        """Create a dedicated IPC socket for a specific session."""
        if os.name == 'nt':
            return None

        socket_path_obj = _safe_session_path(self.working_dir / "sockets", session_id, ".sock")
        socket_path_obj.parent.mkdir(parents=True, exist_ok=True)
        socket_path = str(socket_path_obj)

        # Cleanup if exists (e.g. from a previous crashed run)
        if socket_path_obj.exists():
            socket_path_obj.unlink()

        # Factory for the handler to bind it to this session_id
        async def handler(reader, writer):
            await self._handle_session_request(reader, writer, session_id)

        server = await asyncio.start_unix_server(handler, path=socket_path)
        self._session_servers[session_id] = server
        self._session_sockets[session_id] = socket_path

        return socket_path

    async def _close_session_socket(self, session_id: str) -> Optional[str]:
        """Close and remove a session-specific socket."""
        server = self._session_servers.pop(session_id, None)
        if server:
            server.close()
            await server.wait_closed()

        socket_path = self._session_sockets.pop(session_id, None)
        if socket_path and os.path.exists(socket_path):
            try:
                os.unlink(socket_path)
            except OSError:
                pass

        return socket_path

    _COMMAND_HANDLERS = {
        "spawn": "_handle_spawn_command",
        "wait": "_handle_wait_command",
        "save_checkpoint": "_handle_save_checkpoint",
        "load_checkpoint": "_handle_load_checkpoint",
        "db_query": "_handle_db_query",
        "db_execute": "_handle_db_execute",
        "db_vector_search": "_handle_db_vector",
        "hitl_request": "_handle_hitl_request",
    }

    async def _dispatch_command(self, command: str, request: dict, session_id: str) -> dict:
        """Dispatch an IPC command to its handler."""
        if command in ("db_get", "db_set"):
            op = command[3:]  # "get" or "set"
            return await self._handle_db_nosql(request, op, session_id)
        handler_name = self._COMMAND_HANDLERS.get(command)
        if handler_name is None:
            return {"status": "error", "error": f"Unknown command: {command}"}
        return await getattr(self, handler_name)(request, session_id)

    async def _read_and_dispatch(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter, session_id: str) -> None:
        """Read one framed request, dispatch it, and write the response."""
        import json
        length_data = await reader.readexactly(4)
        message_length = struct.unpack(">I", length_data)[0]

        if message_length > 128 * 1024 * 1024:
            logger.error("Refusing massive IPC payload: %d bytes", message_length)
            raise ValueError(f"IPC payload too large: {message_length} bytes")

        data = await reader.readexactly(message_length)
        try:
            request = json.loads(data.decode())
        except json.JSONDecodeError:
            return

        response = await self._dispatch_command(request.get("command") or "", request, session_id)
        encoded = json.dumps(response).encode()
        writer.write(struct.pack(">I", len(encoded)) + encoded)
        await writer.drain()

    async def _handle_session_request(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter, session_id: str
    ) -> None:
        """Handle one IPC connection: read, dispatch, respond, then close."""
        try:
            await self._read_and_dispatch(reader, writer, session_id)
        except asyncio.IncompleteReadError:
            pass
        except Exception as e:
            logger.error("IPC Error for session %s: %s", session_id, e)
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except Exception as e:
                logger.debug("writer.wait_closed() failed: %s", e)

    async def _handle_spawn_command(self, request: dict, parent_session_id: str) -> dict:
        logger.info(f"Received spawn request from session {parent_session_id}")
        policy_dict = request.get("policy")
        spawn_policy = Policy(**policy_dict) if policy_dict else Policy()
        
        # Recursive Resource Enforcement (v0.2.1)
        # Check if the parent session has enough budget for this sub-agent
        budget = self.session_manager.get_remaining_budget(parent_session_id)
        
        if spawn_policy.cpu_cores > budget["cpu"]:
            return {
                "status": "error",
                "error": f"Resource limit exceeded: parent has {budget['cpu']} cores remaining, requested {spawn_policy.cpu_cores}"
            }
        
        if spawn_policy.memory_mb > budget["memory"]:
            return {
                "status": "error",
                "error": f"Resource limit exceeded: parent has {budget['memory']} MB remaining, requested {spawn_policy.memory_mb} MB"
            }

        agent_payload_hex = request.get("agent_payload")
        
        if agent_payload_hex:
            import uuid
            new_session_id = str(uuid.uuid4())
            
            # Start agent in background
            async def run_and_track():
                try:
                    # Create socket for the new sub-agent too
                    socket_path = await self._create_session_socket(new_session_id)
                    from isolated_agents_sdk import async_run_agent
                    result = await async_run_agent(
                        agent=None,
                        working_dir=self.working_dir,
                        policy=spawn_policy,
                        agent_payload_hex=agent_payload_hex,
                        spawn_socket_path=socket_path,
                        audit_logger=self.audit_logger,
                        session_id=new_session_id,
                        parent_session_id=parent_session_id # Pass parent ID for resource tracking
                    )
                    self._job_results[new_session_id] = result
                except Exception as e:
                    logger.error(f"Background agent failure: {e}")
                finally:
                    await self._close_session_socket(new_session_id)
                    if new_session_id in self._active_jobs:
                        del self._active_jobs[new_session_id]

            task = asyncio.create_task(run_and_track())
            self._active_jobs[new_session_id] = task
            
            return {
                "status": "success",
                "session_id": new_session_id,
                "message": "Sub-agent spawned in background"
            }
        return {"error": "Missing agent_payload"}

    async def _handle_wait_command(self, request: dict, session_id: str) -> dict:
        target_session_id = request.get("target_session_id")
        if not target_session_id:
            return {"status": "error", "error": "Missing target_session_id"}
            
        # Wait for the task if it's still running
        if target_session_id in self._active_jobs:
            try:
                await self._active_jobs[target_session_id]
            except Exception as e:
                return {"status": "error", "error": str(e)}
                
        # Return the collected result
        result = self._job_results.get(target_session_id)
        if result:
            return {
                "status": "success",
                "session_id": result.session_id,
                "exit_code": result.exit_code,
                "output": result.output,
                "artifacts": result.artifacts
            }
        return {"status": "error", "error": "Job result not found"}

    async def _handle_save_checkpoint(self, request: dict, session_id: str) -> dict:
        data_payload = request.get("data_payload")
        if not data_payload:
            return {"status": "error", "error": "Missing data_payload"}
        # data_payload is a hex-encoded cloudpickle blob — store as binary to prevent injection.
        try:
            checkpoint_file = _safe_session_path(self.state_dir, session_id, ".checkpoint")
            checkpoint_file.write_bytes(bytes.fromhex(data_payload))
            return {"status": "success"}
        except (ValueError, OSError) as e:
            return {"status": "error", "error": str(e)}

    async def _handle_load_checkpoint(self, request: dict, session_id: str) -> dict:
        try:
            checkpoint_file = _safe_session_path(self.state_dir, session_id, ".checkpoint")
        except ValueError as e:
            return {"status": "error", "error": str(e)}
        if not checkpoint_file.exists():
            return {"status": "error", "error": "Checkpoint not found"}
        try:
            return {"status": "success", "data_payload": checkpoint_file.read_bytes().hex()}
        except OSError as e:
            return {"status": "error", "error": str(e)}

    def _check_db_access(self, session_id: Optional[str], db_id: str) -> bool:
        """Verify that a session is allowed to access a specific database."""
        if not session_id:
            return False
            
        policy = self.session_manager.get_session_policy(session_id)
        if not policy:
            # might be a sub-agent situation where we don't have the policy readily available 
            # if it was spawned via another mechanism, but usually we should.
            # For now, if no policy, deny.
            return False
            
        # Check if db_id is in the policy's database_access dictionary
        return db_id in policy.database_access

    def _validate_sql_query(self, query: str) -> None:
        """Heuristic check for basic SQL injection patterns (v0.2.1 Hardening)."""
        import re
        # Detect suspicious patterns: semicolons, comments, destructive commands
        # and unauthorized system information discovery.
        lowered = query.lower()
        forbidden_patterns = [
            r";\s*drop\b",
            r";\s*truncate\b",
            r";\s*delete\b",
            r";\s*update\b",
            r";\s*insert\b",
            r";\s*exec\b",
            r";\s*execute\b",
            r"--",      # SQL single-line comment
            r"/\*",     # SQL multi-line comment start
            r"\*/",     # SQL multi-line comment end
            r"xp_cmdshell", # SQL Server shell execution
            r"information_schema", # Metadata discovery
            r"pg_sleep", # Postgres time-based blind injection
            r"sleep\(",  # MySQL time-based blind injection
        ]
        
        for pattern in forbidden_patterns:
            if re.search(pattern, lowered):
                raise ValueError(f"Potentially unsafe SQL query detected (pattern: {pattern})")

    async def _handle_db_query(self, request: dict[str, Any], session_id: str) -> dict[str, Any]:
        """Process a database query request with security checks."""
        db_id = request.get("db_id")
        query = request.get("query")
        params = request.get("params", {})
        
        if not db_id:
            return {"status": "error", "error": "Missing db_id"}
            
        if not self._check_db_access(session_id, db_id):
            return {"status": "error", "error": f"Access denied to database '{db_id}' for session '{session_id}'"}
            
        if not query:
            return {"status": "error", "error": "Missing query"}
        try:
            self._validate_sql_query(query)
            from isolated_agents_sdk.adapters.registry import get_registry
            adapter = get_registry().get_database_adapter(db_id)
            results = await adapter.query(query, **params)
            return {"status": "success", "results": results}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    async def _handle_db_execute(self, request: dict[str, Any], session_id: str) -> dict[str, Any]:
        """Process a database execute request with security checks."""
        db_id = request.get("db_id")
        query = request.get("query")
        params = request.get("params", {})

        if not db_id:
            return {"status": "error", "error": "Missing db_id"}

        if not self._check_db_access(session_id, db_id):
            return {"status": "error", "error": f"Access denied to database '{db_id}' for session '{session_id}'"}

        if not query:
            return {"status": "error", "error": "Missing query"}
        try:
            self._validate_sql_query(query)
            from isolated_agents_sdk.adapters.registry import get_registry
            adapter = get_registry().get_database_adapter(db_id)
            rowcount = await adapter.execute(query, **params)
            return {"status": "success", "rowcount": rowcount}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    async def _handle_db_nosql(self, request: dict[str, Any], op: str, session_id: str) -> dict[str, Any]:
        """Process NoSQL database requests with security checks."""
        db_id = request.get("db_id")
        
        if not db_id:
            return {"status": "error", "error": "Missing db_id"}

        if not self._check_db_access(session_id, db_id):
            return {"status": "error", "error": f"Access denied to database '{db_id}' for session '{session_id}'"}
            
        try:
            from isolated_agents_sdk.adapters.registry import get_registry
            registry = get_registry()
            adapter = registry.get_database_adapter(db_id)
            
            from isolated_agents_sdk.adapters.database.nosql import NoSQLDatabaseAdapter
            if not isinstance(adapter, NoSQLDatabaseAdapter):
                return {"status": "error", "error": f"Adapter '{db_id}' is not a NoSQL adapter"}
                
            if op == "get":
                key = request.get("key")
                if not key:
                    return {"status": "error", "error": "Missing key"}
                value = await adapter.query(key, {"collection": request.get("collection")})
                return {"status": "success", "value": value}
            elif op == "set":
                await adapter.execute("set", {"key": request.get("key"), "value": request.get("value"), "collection": request.get("collection")})
                return {"status": "success"}
            return {"status": "error", "error": f"Unknown NoSQL operation: {op}"}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    async def _handle_db_vector(self, request: dict[str, Any], session_id: str) -> dict[str, Any]:
        """Process vector database requests with security checks."""
        db_id = request.get("db_id")
        
        if not db_id:
            return {"status": "error", "error": "Missing db_id"}

        if not self._check_db_access(session_id, db_id):
            return {"status": "error", "error": f"Access denied to database '{db_id}' for session '{session_id}'"}
            
        try:
            from isolated_agents_sdk.adapters.registry import get_registry
            registry = get_registry()
            adapter = registry.get_database_adapter(db_id)
            
            from isolated_agents_sdk.adapters.database.vector import VectorDatabaseAdapter
            if not isinstance(adapter, VectorDatabaseAdapter):
                return {"status": "error", "error": f"Adapter '{db_id}' is not a Vector adapter"}
                
            results = await adapter.query(
                request.get("query_vector"),
                {"top_k": request.get("limit", 5), "collection": request.get("collection")},
            )
            return {"status": "success", "results": results}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    @property
    def spawn_socket_path(self) -> Optional[str]:
        return self._spawn_socket_path

    def register_hitl_handler(self, handler: Callable[[str, str, int], Awaitable[str]]) -> None:
        """Register a handler for Human-in-the-Loop (HITL) requests.
        
        Args:
            handler: An async function that takes (session_id, prompt, timeout) and returns a human input string.
        """
        self._hitl_handler = handler

    def list_sessions(self) -> List[SessionInfo]:
        """List all active agent sessions in this runtime."""
        return self.session_manager.list_sessions()

    async def cancel_session(self, session_id: str) -> bool:
        """Cancel a running agent session."""
        logger.warning(f"Request to cancel session {session_id}")
        await self.session_manager.complete_session(session_id, exit_code=1, error="Cancelled by runtime.")
        return True

    def get_status(self) -> Dict[str, Any]:
        """Get the current operational status of the runtime."""
        sessions = self.list_sessions()
        
        # Calculate uptime and resource metrics
        active_count = len(sessions)
        
        return {
            "runtime_id": self.runtime_id,
            "active_sessions": active_count,
            "is_running": self._is_running,
            "socket_active": self._spawn_server is not None,
            "workspace": str(self.working_dir),
            "telemetry": {
                "total_executions": self.audit_logger._metrics.get("total_runs", 0) if hasattr(self.audit_logger, "_metrics") else 0,
                "violation_count": self.audit_logger._metrics.get("violations", 0) if hasattr(self.audit_logger, "_metrics") else 0,
            }
        }
