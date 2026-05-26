"""Built-in Agent Runtime for the Isolated Agents SDK.

Provides a unified high-level interface for managing agent sessions, 
sub-agent spawning, and background orchestration.
"""

from __future__ import annotations

import asyncio
import logging
import os
import socket
import struct
import tempfile
import uuid
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from isolated_agents_sdk.agent_runner import AgentRunner
from isolated_agents_sdk.audit_logger import AuditLogger
from isolated_agents_sdk.container_provisioner import ContainerProvisioner
from isolated_agents_sdk.models import AgentResult, Policy, SessionInfo
from isolated_agents_sdk.session_manager import SessionManager
from isolated_agents_sdk.logging import get_logger

logger = get_logger("runtime")

_GLOBAL_RUNTIME: Optional[AgentRuntime] = None

def get_runtime(working_dir: Optional[str | Path] = None) -> AgentRuntime:
    """Get or create the global AgentRuntime instance."""
    global _GLOBAL_RUNTIME
    if _GLOBAL_RUNTIME is None:
        _GLOBAL_RUNTIME = AgentRuntime(working_dir=working_dir or "./runtime_workspace")
    return _GLOBAL_RUNTIME

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

    async def _create_session_socket(self, session_id: str) -> str:
        """Create a dedicated IPC socket for a specific session."""
        if os.name == 'nt':
            # On Windows, we still don't have a clean way for untrusted containers 
            # to talk to host via UDS in a cross-platform manner without complex setup.
            return None

        socket_path_obj = self.working_dir / "sockets" / f"{session_id}.sock"
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

    async def _close_session_socket(self, session_id: str) -> None:
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

    async def _handle_session_request(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter, session_id: str
    ) -> None:
        """Handle IPC requests using length-prefixed framing (v0.2.1 Hardening)."""
        try:
            # 1. Read the length-prefix (4-byte big-endian)
            # This allows us to handle payloads > 1MB safely.
            length_data = await reader.readexactly(4)
            message_length = struct.unpack(">I", length_data)[0]
            
            # Security: Sanity check on message length (limit to 128MB)
            if message_length > 128 * 1024 * 1024:
                logger.error(f"Refusing massive IPC payload: {message_length} bytes")
                return

            # 2. Read the full message body
            data = await reader.readexactly(message_length)
            if not data:
                return
                
            import json
            try:
                request = json.loads(data.decode())
            except json.JSONDecodeError:
                return

            command = request.get("command")
            response = {"status": "error", "error": f"Unknown command: {command}"}

            if command == "spawn":
                response = await self._handle_spawn_command(request, session_id)
            elif command == "wait":
                response = await self._handle_wait_command(request, session_id)
            elif command == "save_checkpoint":
                response = await self._handle_save_checkpoint(request, session_id)
            elif command == "load_checkpoint":
                response = await self._handle_load_checkpoint(request, session_id)
            elif command == "db_query":
                response = await self._handle_db_query(request, session_id)
            elif command == "db_execute":
                response = await self._handle_db_execute(request, session_id)
            elif command == "db_get":
                response = await self._handle_db_nosql(request, "get", session_id)
            elif command == "db_set":
                response = await self._handle_db_nosql(request, "set", session_id)
            elif command == "db_vector_search":
                response = await self._handle_db_vector(request, session_id)
            elif command == "hitl_request":
                response = await self._handle_hitl_request(request, session_id)

            # 3. Send length-prefixed response
            encoded_response = json.dumps(response).encode()
            writer.write(struct.pack(">I", len(encoded_response)) + encoded_response)
            await writer.drain()
        except asyncio.IncompleteReadError:
            # Normal client disconnection
            pass
        except Exception as e:
            logger.error(f"IPC Error for session {session_id}: {e}")
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass

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
        if data_payload:
            checkpoint_file = self.state_dir / f"{session_id}.checkpoint"
            try:
                with open(checkpoint_file, "w") as f:
                    f.write(data_payload)
                return {"status": "success"}
            except Exception as e:
                return {"status": "error", "error": str(e)}
        return {"status": "error", "error": "Missing data_payload"}

    async def _handle_load_checkpoint(self, request: dict, session_id: str) -> dict:
        checkpoint_file = self.state_dir / f"{session_id}.checkpoint"
        if checkpoint_file.exists():
            try:
                with open(checkpoint_file, "r") as f:
                    data_payload = f.read()
                return {"status": "success", "data_payload": data_payload}
            except Exception as e:
                return {"status": "error", "error": str(e)}
        return {"status": "error", "error": "Checkpoint not found"}

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
            
        try:
            # 1. Basic SQL injection check
            if query:
                self._validate_sql_query(query)

            from isolated_agents_sdk.adapters.registry import get_registry
            registry = get_registry()
            adapter = registry.get_database_adapter(db_id)
            
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
            
        try:
            # 1. Basic SQL injection check
            if query:
                self._validate_sql_query(query)

            from isolated_agents_sdk.adapters.registry import get_registry
            registry = get_registry()
            adapter = registry.get_database_adapter(db_id)
            
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
                value = await adapter.get(request.get("key"), request.get("collection"))
                return {"status": "success", "value": value}
            elif op == "set":
                await adapter.set(request.get("key"), request.get("value"), request.get("collection"))
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
                
            results = await adapter.search(
                request.get("query_vector"), 
                request.get("limit", 5), 
                request.get("collection")
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
