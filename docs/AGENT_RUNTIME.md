# Agent Runtime & Orchestration (v0.2.0)

The **Agent Runtime** is the central nervous system of the Isolated Agents SDK. Introduced in v0.2.0, it transitions the SDK from a library for execution into a professional service for agent orchestration.

---

## 🏗️ Architecture Overview

The v0.2.0 architecture consists of three core background services:

1.  **Agent Runtime**: Manages global session state, persistent working directories, and lifecycle events.
2.  **Spawn Daemon**: A Unix Domain Socket IPC server that facilitates **secure container-to-host recursion**.
3.  **Agent Scheduler**: A background task engine for recurring intervals and delayed execution.

---

## 🚀 The Agent Runtime

The `AgentRuntime` class provides a unified high-level interface.

### Starting the Runtime

```python
from isolated_agents_sdk import AgentRuntime

runtime = AgentRuntime(working_dir="./prod_workspace")

# Start background services (Spawn Daemon, etc.)
await runtime.start()

# Status check
print(runtime.get_status())
```

### Running Agents via Runtime

Running an agent through the runtime ensures it is tracked and can use the Spawn Daemon for recursion.

```python
from isolated_agents_sdk import Policy

policy = Policy(allow_sub_agents=True)

# Run an agent
result = await runtime.run_agent(
    agent=my_agent_func,
    policy=policy
)
```

---

## 🧵 Sub-Agent Nesting (Spawn Daemon)

Agents running inside isolation can now securely spawn their own sub-agents.

### Internal Agent Logic
Inside your agent function, use the `spawn_sub_agent` utility:

```python
from isolated_agents_sdk.sub_agent_client import spawn_sub_agent

def parent_agent():
    print("Spawning child...")
    result = spawn_sub_agent(
        agent=child_agent_logic,
        policy=Policy(memory_mb=128)
    )
    return f"Child finished with: {result.exit_code}"
```

---

## ⏰ Background Scheduling

The `AgentScheduler` enables cron-like behavior for agent automation.

```python
from isolated_agents_sdk import AgentScheduler

scheduler = AgentScheduler()

# Every 5 minutes
await scheduler.schedule_agent_interval(
    interval_seconds=300,
    agent=cleanup_script
)

# 10 second delay
await scheduler.schedule_agent_in(
    delay_seconds=10,
    agent=one_off_task
)
```

---

## 📊 Structured JSON Logging

For production environments, enable machine-readable logs.

```python
from isolated_agents_sdk import setup_logging

# Enable structured JSON output
setup_logging(structured=True, level="INFO")
```

Example Output:
```json
{"timestamp": "2026-05-22T14:30:00.123Z", "level": "INFO", "logger": "runtime", "message": "Agent session started", "session_id": "abc-123"}
```
