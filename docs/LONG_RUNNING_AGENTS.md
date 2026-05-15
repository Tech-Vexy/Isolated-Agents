# Long-Running Agents and Sub-Agents

## Overview

The Isolated Agents SDK provides robust support for:

- **Long-running agents** - Agents that run for extended periods (hours, days)
- **Sub-agents** - Hierarchical agent spawning with nesting limits
- **Session management** - Track and manage multiple concurrent sessions
- **Resource monitoring** - Continuous monitoring of CPU and memory
- **Timeout handling** - Automatic termination of runaway agents
- **Graceful shutdown** - Clean termination on signals (SIGTERM, SIGINT)

---

## Long-Running Agents

### Overview

Long-running agents are designed for tasks that take significant time:

- **Data processing pipelines** - Process large datasets over hours
- **Monitoring services** - Continuously monitor systems
- **Background workers** - Process queues and jobs
- **Scheduled tasks** - Run periodic operations
- **Streaming applications** - Handle real-time data streams

### Key Features

1. **Extended timeouts** - Configure timeouts up to days
2. **Resource monitoring** - Track CPU/memory usage continuously
3. **Graceful shutdown** - Handle termination signals properly
4. **Session persistence** - Maintain state across restarts
5. **Progress tracking** - Report progress during execution
6. **Error recovery** - Automatic retry on failures

---

## Configuration

### Basic Long-Running Agent

```python
from isolated_agents_sdk import run_agent, Policy
from pathlib import Path
import time

def long_running_agent():
    """Agent that runs for an extended period."""
    from pathlib import Path
    import time
    
    output_dir = Path("/output")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Simulate long-running task
    for i in range(100):
        # Do work
        time.sleep(10)  # 10 seconds per iteration
        
        # Report progress
        progress = (i + 1) / 100 * 100
        (output_dir / "progress.txt").write_text(f"{progress:.1f}%")
        print(f"Progress: {progress:.1f}%")
    
    (output_dir / "result.txt").write_text("Completed!")

# Run with extended timeout
result = run_agent(
    agent=long_running_agent,
    working_dir="./workspace",
    host_output_path="./output",
    policy=Policy(
        timeout_seconds=3600,  # 1 hour timeout
        resource_monitor_interval=30,  # Check resources every 30s
        cpu_threshold_percent=90.0,  # Alert if CPU > 90%
        memory_threshold_percent=90.0,  # Alert if memory > 90%
    )
)
```

### Advanced Configuration

```python
from isolated_agents_sdk import Policy, NetworkPolicy

policy = Policy(
    # Extended timeout for long-running tasks
    timeout_seconds=86400,  # 24 hours
    
    # Resource limits
    cpu_cores=4.0,
    memory_mb=8192,
    
    # Resource monitoring
    resource_monitor_interval=60,  # Check every minute
    cpu_threshold_percent=85.0,
    memory_threshold_percent=85.0,
    
    # Network access for external services
    network=NetworkPolicy(
        disabled=False,
        allowed_endpoints=["api.example.com:443"]
    ),
    
    # Environment variables
    allowed_env_vars=["API_KEY", "DATABASE_URL"],
    
    # Dependencies
    pip_packages=["requests", "pandas", "sqlalchemy"],
)
```

---

## Sub-Agents

### Overview

Sub-agents allow hierarchical agent spawning where a parent agent can spawn child agents:

- **Hierarchical workflows** - Break complex tasks into subtasks
- **Parallel processing** - Spawn multiple agents for parallel work
- **Resource isolation** - Each sub-agent has its own container
- **Nesting limits** - Prevent infinite recursion
- **Count limits** - Limit total sub-agents per session

### Architecture

```
Parent Agent (depth 0)
├── Sub-Agent 1 (depth 1)
│   ├── Sub-Agent 1.1 (depth 2)
│   └── Sub-Agent 1.2 (depth 2)
├── Sub-Agent 2 (depth 1)
│   └── Sub-Agent 2.1 (depth 2)
│       └── Sub-Agent 2.1.1 (depth 3) ← max_sub_agent_depth
└── Sub-Agent 3 (depth 1)
```

### Configuration

```python
from isolated_agents_sdk import Policy, SubAgentPolicy

parent_policy = Policy(
    # Sub-agent limits
    max_sub_agent_depth=3,  # Maximum nesting depth
    max_sub_agents=10,      # Maximum total sub-agents
    
    # Parent resources
    cpu_cores=8.0,
    memory_mb=16384,
)

sub_agent_policy = SubAgentPolicy(
    # Sub-agent resources (clamped to parent limits)
    cpu_cores=2.0,
    memory_mb=2048,
    
    # Sub-agent timeout
    timeout_seconds=600,
    
    # Nested sub-agents
    max_sub_agent_depth=2,  # Remaining depth
    max_sub_agents=5,       # Remaining count
)
```

---

## Examples

### Example 1: Data Processing Pipeline

```python
"""Long-running data processing pipeline."""

from isolated_agents_sdk import run_agent, Policy
from pathlib import Path
import time

def data_processor():
    """Process large dataset over extended period."""
    import pandas as pd
    from pathlib import Path
    import time
    
    output_dir = Path("/output")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Load large dataset
    data_path = Path("/workspace/large_dataset.csv")
    df = pd.read_csv(data_path)
    
    total_rows = len(df)
    batch_size = 1000
    
    results = []
    
    # Process in batches
    for i in range(0, total_rows, batch_size):
        batch = df.iloc[i:i+batch_size]
        
        # Process batch (simulate work)
        processed = batch.apply(lambda x: x * 2)
        results.append(processed)
        
        # Report progress
        progress = min((i + batch_size) / total_rows * 100, 100)
        (output_dir / "progress.txt").write_text(f"{progress:.1f}%")
        print(f"Processed {i+batch_size}/{total_rows} rows ({progress:.1f}%)")
        
        # Small delay to simulate processing time
        time.sleep(1)
    
    # Save results
    result_df = pd.concat(results)
    result_df.to_csv(output_dir / "processed_data.csv", index=False)
    
    (output_dir / "summary.txt").write_text(
        f"Processed {total_rows} rows in {len(results)} batches"
    )

# Run with extended timeout
result = run_agent(
    agent=data_processor,
    working_dir="./data",
    host_output_path="./output",
    policy=Policy(
        timeout_seconds=7200,  # 2 hours
        cpu_cores=4.0,
        memory_mb=8192,
        resource_monitor_interval=60,
        pip_packages=["pandas"],
    )
)

print(f"Processing completed: {result.exit_code == 0}")
```

### Example 2: Hierarchical Sub-Agents

```python
"""Hierarchical agent system with sub-agents."""

from isolated_agents_sdk import run_agent, Policy, SubAgentPolicy
from pathlib import Path

def parent_agent():
    """Parent agent that spawns sub-agents."""
    from isolated_agents_sdk import spawn_sub_agent, SubAgentPolicy
    from pathlib import Path
    
    output_dir = Path("/output")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Define sub-agent tasks
    tasks = [
        "Analyze data segment 1",
        "Analyze data segment 2",
        "Analyze data segment 3",
    ]
    
    results = []
    
    # Spawn sub-agents for each task
    for i, task in enumerate(tasks):
        print(f"Spawning sub-agent {i+1} for: {task}")
        
        # Define sub-agent function
        def sub_agent_task():
            from pathlib import Path
            import time
            
            # Simulate work
            time.sleep(5)
            
            # Save result
            output_dir = Path("/output")
            output_dir.mkdir(parents=True, exist_ok=True)
            (output_dir / f"result_{i}.txt").write_text(f"Completed: {task}")
        
        # Spawn sub-agent
        sub_result = spawn_sub_agent(
            agent=sub_agent_task,
            policy=SubAgentPolicy(
                cpu_cores=1.0,
                memory_mb=1024,
                timeout_seconds=300,
            )
        )
        
        results.append(sub_result)
    
    # Aggregate results
    (output_dir / "summary.txt").write_text(
        f"Completed {len(results)} sub-tasks"
    )

# Run parent agent
result = run_agent(
    agent=parent_agent,
    working_dir="./workspace",
    host_output_path="./output",
    policy=Policy(
        cpu_cores=4.0,
        memory_mb=4096,
        max_sub_agent_depth=2,
        max_sub_agents=10,
        timeout_seconds=1800,
    )
)
```

### Example 3: Monitoring Service

```python
"""Long-running monitoring service."""

from isolated_agents_sdk import run_agent, Policy, NetworkPolicy
from pathlib import Path

def monitoring_agent():
    """Monitor external service continuously."""
    import requests
    import time
    from pathlib import Path
    from datetime import datetime
    
    output_dir = Path("/output")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    log_file = output_dir / "monitor.log"
    
    # Monitor for 1 hour
    end_time = time.time() + 3600
    check_interval = 60  # Check every minute
    
    while time.time() < end_time:
        try:
            # Check service health
            response = requests.get("https://api.example.com/health", timeout=10)
            status = "UP" if response.status_code == 200 else "DOWN"
            
            # Log result
            timestamp = datetime.now().isoformat()
            log_entry = f"{timestamp} - Status: {status}\n"
            
            with open(log_file, "a") as f:
                f.write(log_entry)
            
            print(log_entry.strip())
            
        except Exception as e:
            # Log error
            timestamp = datetime.now().isoformat()
            log_entry = f"{timestamp} - Error: {str(e)}\n"
            
            with open(log_file, "a") as f:
                f.write(log_entry)
            
            print(log_entry.strip())
        
        # Wait before next check
        time.sleep(check_interval)
    
    (output_dir / "summary.txt").write_text("Monitoring completed")

# Run monitoring agent
result = run_agent(
    agent=monitoring_agent,
    working_dir="./workspace",
    host_output_path="./output",
    policy=Policy(
        timeout_seconds=3700,  # Slightly longer than monitoring period
        network=NetworkPolicy(
            disabled=False,
            allowed_endpoints=["api.example.com:443"]
        ),
        resource_monitor_interval=300,  # Check resources every 5 minutes
        pip_packages=["requests"],
    )
)
```

### Example 4: Parallel Sub-Agents

```python
"""Parallel processing with multiple sub-agents."""

from isolated_agents_sdk import run_agent, Policy
from pathlib import Path

def parallel_coordinator():
    """Coordinate parallel sub-agents."""
    from isolated_agents_sdk import spawn_sub_agent, SubAgentPolicy
    from pathlib import Path
    import concurrent.futures
    
    output_dir = Path("/output")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Define work items
    work_items = list(range(10))
    
    def process_item(item_id):
        """Sub-agent to process one item."""
        from pathlib import Path
        import time
        
        # Simulate processing
        time.sleep(2)
        
        # Save result
        output_dir = Path("/output")
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / f"item_{item_id}.txt").write_text(f"Processed item {item_id}")
        
        return item_id
    
    # Spawn sub-agents in parallel
    results = []
    for item_id in work_items:
        result = spawn_sub_agent(
            agent=lambda: process_item(item_id),
            policy=SubAgentPolicy(
                cpu_cores=0.5,
                memory_mb=512,
                timeout_seconds=60,
            )
        )
        results.append(result)
    
    # Wait for all to complete
    completed = sum(1 for r in results if r.status == "completed")
    
    (output_dir / "summary.txt").write_text(
        f"Completed {completed}/{len(work_items)} items"
    )

# Run coordinator
result = run_agent(
    agent=parallel_coordinator,
    working_dir="./workspace",
    host_output_path="./output",
    policy=Policy(
        cpu_cores=8.0,
        memory_mb=8192,
        max_sub_agents=20,
        timeout_seconds=600,
    )
)
```

---

## Session Management

### Listing Active Sessions

```python
from isolated_agents_sdk import SessionManager

manager = SessionManager()

# Get all active sessions
sessions = manager.list_sessions()

for session in sessions:
    print(f"Session: {session.session_id}")
    print(f"  Status: {session.status}")
    print(f"  Started: {session.started_at}")
    print(f"  Container: {session.container_id}")
    
    # List sub-sessions
    for sub in session.sub_sessions:
        print(f"  Sub-session: {sub.sub_session_id}")
        print(f"    Status: {sub.status}")
        print(f"    Depth: {sub.nesting_depth}")
```

### Cancelling Sessions

```python
from isolated_agents_sdk import SessionManager

manager = SessionManager()

# Cancel a specific session
manager.cancel_session("session-123")

# Cancel all sessions
for session in manager.list_sessions():
    manager.cancel_session(session.session_id)
```

### Monitoring Resources

```python
from isolated_agents_sdk import SessionManager

manager = SessionManager()

# Get resource metrics for a session
metrics = manager.get_session_metrics("session-123")

print(f"CPU: {metrics.cpu_percent}%")
print(f"Memory: {metrics.memory_mb} MB")
```

---

## Best Practices

### 1. Set Appropriate Timeouts

```python
# Short tasks (< 5 minutes)
policy = Policy(timeout_seconds=300)

# Medium tasks (5-60 minutes)
policy = Policy(timeout_seconds=3600)

# Long tasks (1-24 hours)
policy = Policy(timeout_seconds=86400)

# Very long tasks (> 24 hours)
policy = Policy(timeout_seconds=604800)  # 1 week
```

### 2. Monitor Resources

```python
policy = Policy(
    # Check resources frequently for long-running agents
    resource_monitor_interval=60,  # Every minute
    
    # Set conservative thresholds
    cpu_threshold_percent=80.0,
    memory_threshold_percent=80.0,
)
```

### 3. Report Progress

```python
def long_task():
    from pathlib import Path
    
    output_dir = Path("/output")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    total = 100
    for i in range(total):
        # Do work
        process_item(i)
        
        # Report progress
        progress = (i + 1) / total * 100
        (output_dir / "progress.txt").write_text(f"{progress:.1f}%")
        
        # Also log to stdout
        if (i + 1) % 10 == 0:
            print(f"Progress: {progress:.1f}%")
```

### 4. Handle Graceful Shutdown

```python
def graceful_agent():
    import signal
    import sys
    from pathlib import Path
    
    shutdown_requested = False
    
    def signal_handler(signum, frame):
        nonlocal shutdown_requested
        shutdown_requested = True
        print("Shutdown requested, cleaning up...")
    
    # Register signal handlers
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    output_dir = Path("/output")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    try:
        for i in range(1000):
            if shutdown_requested:
                # Save state before exiting
                (output_dir / "state.txt").write_text(f"Stopped at iteration {i}")
                break
            
            # Do work
            process_item(i)
        
        (output_dir / "result.txt").write_text("Completed")
    
    finally:
        # Cleanup
        cleanup_resources()
```

### 5. Limit Sub-Agent Nesting

```python
policy = Policy(
    # Prevent deep nesting
    max_sub_agent_depth=3,
    
    # Limit total sub-agents
    max_sub_agents=20,
)
```

### 6. Use Sub-Agent Policies

```python
# Parent policy
parent_policy = Policy(
    cpu_cores=8.0,
    memory_mb=16384,
    max_sub_agents=10,
)

# Sub-agent policy (automatically clamped to parent limits)
sub_policy = SubAgentPolicy(
    cpu_cores=2.0,  # Will be clamped if parent has less
    memory_mb=2048,
    timeout_seconds=300,
)
```

---

## Troubleshooting

### Timeout Issues

```python
# Problem: Agent times out
policy = Policy(timeout_seconds=300)  # Too short

# Solution: Increase timeout
policy = Policy(timeout_seconds=3600)  # 1 hour
```

### Resource Exhaustion

```python
# Problem: Agent uses too much memory
policy = Policy(memory_mb=1024)  # Too little

# Solution: Increase memory limit
policy = Policy(memory_mb=4096)
```

### Sub-Agent Limits

```python
# Problem: Cannot spawn more sub-agents
# Error: "sub_agent_count_exceeded"

# Solution: Increase limits
policy = Policy(
    max_sub_agents=50,  # Increase from default 10
)
```

### Nesting Depth Exceeded

```python
# Problem: Cannot spawn nested sub-agent
# Error: "nesting_depth_exceeded"

# Solution: Increase depth or flatten hierarchy
policy = Policy(
    max_sub_agent_depth=5,  # Increase from default 3
)
```

---

## API Reference

### Policy Parameters

```python
Policy(
    # Timeout
    timeout_seconds: Optional[int] = None,
    
    # Resource limits
    cpu_cores: float = 1.0,
    memory_mb: int = 512,
    
    # Resource monitoring
    resource_monitor_interval: int = 5,
    cpu_threshold_percent: float = 90.0,
    memory_threshold_percent: float = 90.0,
    
    # Sub-agent limits
    max_sub_agent_depth: int = 3,
    max_sub_agents: int = 10,
)
```

### SubAgentPolicy Parameters

```python
SubAgentPolicy(
    # Resource limits (clamped to parent)
    cpu_cores: float = 1.0,
    memory_mb: int = 512,
    
    # Timeout
    timeout_seconds: Optional[int] = None,
    
    # Nested sub-agents
    max_sub_agent_depth: int = 3,
    max_sub_agents: int = 10,
)
```

### SessionManager Methods

```python
# List all sessions
sessions = manager.list_sessions()

# Get session info
info = manager.get_session("session-123")

# Cancel session
manager.cancel_session("session-123")

# Get metrics
metrics = manager.get_session_metrics("session-123")
```

---

## Summary

The Isolated Agents SDK provides comprehensive support for:

- ✅ **Long-running agents** with extended timeouts
- ✅ **Sub-agent spawning** with hierarchical workflows
- ✅ **Resource monitoring** with continuous tracking
- ✅ **Session management** with full lifecycle control
- ✅ **Graceful shutdown** with signal handling
- ✅ **Progress tracking** with real-time updates
- ✅ **Nesting limits** to prevent infinite recursion
- ✅ **Count limits** to control resource usage

For more information, see:
- [Architecture](ADAPTER_ARCHITECTURE.md)
- [Production Ready Summary](PRODUCTION_READY_SUMMARY.md)
- [Examples Catalog](EXAMPLES_CATALOG.md)