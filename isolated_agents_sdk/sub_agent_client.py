"""Sub-Agent Client for in-sandbox recursion.

Enables an agent running inside an isolated container to spawn its own
sub-agents by communicating with the host-side Spawn Daemon.
"""

from __future__ import annotations

import json
import logging
import os
import socket
from typing import Any, Dict, Optional

from isolated_agents_sdk.models import AgentResult, Policy

logger = logging.getLogger(__name__)

_global_client: SubAgentClient | None = None
_DEFAULT_SOCKET_TIMEOUT = 30.0  # seconds


def init_sub_agent_client(socket_path: str) -> None:
    """Initialize the global sub-agent client inside the container."""
    global _global_client
    _global_client = SubAgentClient(socket_path)


def _get_client() -> SubAgentClient:
    """Return the global client, initialising it from the environment if needed."""
    global _global_client
    if _global_client is None:
        socket_path = os.environ.get("ISOLATED_AGENTS_SPAWN_SOCKET")
        if not socket_path:
            raise RuntimeError(
                "Sub-Agent Client not initialized and ISOLATED_AGENTS_SPAWN_SOCKET env var not found."
            )
        _global_client = SubAgentClient(socket_path)
    return _global_client


def spawn_sub_agent(
    agent: Any | None = None,
    policy: Policy | None = None,
    args: tuple = (),
    kwargs: dict[str, Any] | None = None,
) -> AgentResult:
    """Spawn a sub-agent from within an isolated environment."""
    return _get_client().spawn(agent, policy, args, kwargs)


def save_checkpoint(data: Any) -> bool:
    """Save a checkpoint of the current agent state to the host."""
    try:
        return _get_client().save_checkpoint(data)
    except Exception:
        return False


def load_checkpoint() -> Any | None:
    """Retrieve the last saved checkpoint for this session."""
    try:
        return _get_client().load_checkpoint()
    except Exception:
        return None


def db_query(db_id: str, query: str, **params) -> list[dict[str, Any]]:
    """Query a host-mediated database."""
    return _get_client().db_query(db_id, query, **params)


def db_execute(db_id: str, query: str, **params) -> int:
    """Execute a statement on a host-mediated database."""
    return _get_client().db_execute(db_id, query, **params)


def db_get(db_id: str, key: str, collection: str | None = None) -> Any | None:
    """Get a document from a host-mediated NoSQL database."""
    return _get_client().db_get(db_id, key, collection)


def db_set(db_id: str, key: str, value: Any, collection: str | None = None) -> None:
    """Set a document in a host-mediated NoSQL database."""
    _get_client().db_set(db_id, key, value, collection)


def db_vector_search(
    db_id: str,
    query_vector: list[float],
    limit: int = 5,
    collection: str | None = None,
) -> list[dict[str, Any]]:
    """Perform a vector search on a host-mediated vector database."""
    return _get_client().db_vector_search(db_id, query_vector, limit, collection)


class SubAgentClient:
    """Client for the Spawn Daemon IPC interface."""

    def __init__(self, socket_path: str) -> None:
        self.socket_path = socket_path

    def _send_request(
        self, payload: dict[str, Any], timeout: float = _DEFAULT_SOCKET_TIMEOUT
    ) -> dict[str, Any]:
        """Send a request to the Spawn Daemon using length-prefixed framing."""
        import struct

        if not hasattr(socket, "AF_UNIX"):
            return {
                "status": "error",
                "error": "Unix domain sockets are not supported on this platform",
            }
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:  # type: ignore[attr-defined]
                sock.settimeout(timeout)
                sock.connect(self.socket_path)

                # 1. Encode payload
                data = json.dumps(payload).encode()

                # 2. Send length-prefixed frame (4-byte big-endian length)
                sock.sendall(struct.pack(">I", len(data)) + data)

                # 3. Read response length frame (ensure exactly 4 bytes)
                resp_len_data = b""
                while len(resp_len_data) < 4:
                    chunk = sock.recv(4 - len(resp_len_data))
                    if not chunk:
                        raise RuntimeError("Spawn Daemon disconnected while reading length frame")
                    resp_len_data += chunk

                resp_len = struct.unpack(">I", resp_len_data)[0]

                # 4. Read response payload
                chunks = []
                bytes_read = 0
                while bytes_read < resp_len:
                    chunk = sock.recv(min(resp_len - bytes_read, 65536))
                    if not chunk:
                        break
                    chunks.append(chunk)
                    bytes_read += len(chunk)

                if bytes_read < resp_len:
                    raise RuntimeError(
                        f"Truncated response from Spawn Daemon: {bytes_read}/{resp_len} bytes"
                    )

                return json.loads(b"".join(chunks).decode())
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def spawn(
        self,
        agent: Any,
        policy: Policy | None = None,
        args: tuple = (),
        kwargs: dict[str, Any] | None = None,
    ) -> AgentResult:
        """Send a spawn request to the host daemon and wait for result."""
        import cloudpickle

        # 1. Initiate Spawn
        payload = {
            "command": "spawn",
            "agent_payload": cloudpickle.dumps(
                {"fn": agent, "args": args, "kwargs": kwargs or {}}
            ).hex(),
            "policy": policy._to_dict() if policy else None,
        }

        response = self._send_request(payload)

        if response.get("status") != "success":
            return AgentResult(
                exit_code=1,
                artifacts={},
                session_id="error",
                output=response.get("error", "Failed to initiate spawn"),
            )

        target_session_id: str = response.get("session_id") or "unknown"

        # 2. Wait for result (Resilient to disconnects)
        # We can retry heartbeats here if we want, but for now just one wait call
        wait_payload = {"command": "wait", "target_session_id": target_session_id}

        # Use a longer timeout or a loop for very long running agents
        wait_response = self._send_request(wait_payload)

        if wait_response.get("status") == "success":
            return AgentResult(
                exit_code=wait_response.get("exit_code", 0),
                artifacts=wait_response.get("artifacts", {}),
                session_id=str(wait_response.get("session_id") or target_session_id),
                output=wait_response.get("output"),
            )
        else:
            return AgentResult(
                exit_code=1,
                artifacts={},
                session_id=target_session_id,
                output=wait_response.get("error", "Failed to get sub-agent result"),
            )

    def save_checkpoint(self, data: Any) -> bool:
        """Send a checkpoint save request to the host daemon."""
        import cloudpickle

        session_id = os.environ.get("ISOLATED_AGENTS_SESSION_ID")
        if not session_id:
            return False

        payload = {
            "command": "save_checkpoint",
            "session_id": session_id,
            "data_payload": cloudpickle.dumps(data).hex(),
        }

        response = self._send_request(payload)
        return response.get("status") == "success"

    def load_checkpoint(self) -> Any | None:
        """Send a checkpoint load request to the host daemon."""
        import cloudpickle

        session_id = os.environ.get("ISOLATED_AGENTS_SESSION_ID")
        if not session_id:
            return None

        payload = {
            "command": "load_checkpoint",
            "session_id": session_id,
        }

        response = self._send_request(payload)
        if response.get("status") == "success" and "data_payload" in response:
            try:
                return cloudpickle.loads(bytes.fromhex(response["data_payload"]))
            except Exception as e:
                logger.warning("Failed to deserialize checkpoint: %s", e)
                return None
        return None

    def db_query(self, db_id: str, query: str, **params) -> list[dict[str, Any]]:
        """Send a database query request."""
        payload = {
            "command": "db_query",
            "db_id": db_id,
            "query": query,
            "params": params,
            "session_id": os.environ.get("ISOLATED_AGENTS_SESSION_ID"),
        }
        response = self._send_request(payload)
        if response.get("status") == "success":
            return response.get("results", [])
        raise RuntimeError(f"Database query failed: {response.get('error')}")

    def db_execute(self, db_id: str, query: str, **params) -> int:
        """Send a database execute request."""
        payload = {
            "command": "db_execute",
            "db_id": db_id,
            "query": query,
            "params": params,
            "session_id": os.environ.get("ISOLATED_AGENTS_SESSION_ID"),
        }
        response = self._send_request(payload)
        if response.get("status") == "success":
            return response.get("rowcount", 0)
        raise RuntimeError(f"Database execution failed: {response.get('error')}")

    def db_get(self, db_id: str, key: str, collection: str | None = None) -> Any:
        """Send a database get request."""
        payload = {
            "command": "db_get",
            "db_id": db_id,
            "key": key,
            "collection": collection,
            "session_id": os.environ.get("ISOLATED_AGENTS_SESSION_ID"),
        }
        response = self._send_request(payload)
        if response.get("status") == "success":
            return response.get("value")
        raise RuntimeError(f"Database get failed: {response.get('error')}")

    def db_set(self, db_id: str, key: str, value: Any, collection: str | None = None) -> None:
        """Send a database set request."""
        payload = {
            "command": "db_set",
            "db_id": db_id,
            "key": key,
            "value": value,
            "collection": collection,
            "session_id": os.environ.get("ISOLATED_AGENTS_SESSION_ID"),
        }
        response = self._send_request(payload)
        if response.get("status") != "success":
            raise RuntimeError(f"Database set failed: {response.get('error')}")

    def db_vector_search(
        self, db_id: str, query_vector: list[float], limit: int = 5, collection: str | None = None
    ) -> list[dict[str, Any]]:
        """Send a database vector search request."""
        payload = {
            "command": "db_vector_search",
            "db_id": db_id,
            "query_vector": query_vector,
            "limit": limit,
            "collection": collection,
            "session_id": os.environ.get("ISOLATED_AGENTS_SESSION_ID"),
        }
        response = self._send_request(payload)
        if response.get("status") == "success":
            return response.get("results", [])
        raise RuntimeError(f"Database vector search failed: {response.get('error')}")
