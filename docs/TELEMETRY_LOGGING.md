# Telemetry Logging - Real-Time Agent Activity Monitoring

## Overview

The Isolated Agents SDK includes a comprehensive telemetry logging system that displays real-time agent activity in the terminal. This gives users immediate visibility into what their agents are doing inside the sandbox environment, making debugging easier and providing transparency into agent operations.

## Features

### Real-Time Terminal Output

The SDK streams telemetry events to the terminal as they occur, showing:
- ✅ Container lifecycle events (provision, start, stop)
- ✅ Agent execution progress
- ✅ Resource usage (CPU, memory)
- ✅ Network activity
- ✅ File operations
- ✅ Policy violations
- ✅ Error conditions

### Visual Formatting

Telemetry output uses color-coded, emoji-enhanced formatting for easy scanning:
- 🚀 **Blue** - Lifecycle events (starting, stopping)
- ✅ **Green** - Success events (completed, passed)
- ⚠️ **Yellow** - Warnings (high resource usage, timeouts)
- ❌ **Red** - Errors (failures, violations)
- 📊 **Cyan** - Metrics (CPU, memory, network)
- 📝 **White** - Info (general activity)

## Example Terminal Output

```
🚀 [15:30:45] Initializing isolated sandbox...
   ├─ Container Runtime: Podman
   ├─ Storage Backend: Local Filesystem
   └─ Audit Logger: File

🔧 [15:30:46] Validating policy...
   ├─ CPU Limit: 2.0 cores
   ├─ Memory Limit: 1024 MB
   ├─ Network: Disabled
   └─ Timeout: 300 seconds

📦 [15:30:47] Provisioning container...
   ├─ Image: python:3.11-slim
   ├─ Container ID: abc123def456
   └─ Status: Running

📥 [15:30:48] Injecting agent code...
   ├─ Agent: langchain_research_agent
   ├─ Size: 2.4 KB
   └─ Dependencies: langchain, langchain-openai

🔌 [15:30:49] Installing dependencies...
   ├─ Package: langchain==0.1.0
   ├─ Package: langchain-openai==0.0.5
   └─ Status: Installed (12.3 MB)

🚀 [15:30:52] Starting agent execution...
   └─ Command: python3 /tmp/_agent_bootstrap.py

📊 [15:30:53] Resource usage:
   ├─ CPU: 15.2%
   ├─ Memory: 156 MB / 1024 MB (15%)
   └─ Network: 0 B sent, 0 B received

📝 [15:30:55] Agent activity:
   └─ Reading file: /workspace/data.csv

🌐 [15:30:57] Network request:
   ├─ Destination: api.openai.com:443
   ├─ Method: POST
   └─ Status: Allowed

📊 [15:31:00] Resource usage:
   ├─ CPU: 45.8%
   ├─ Memory: 312 MB / 1024 MB (30%)
   └─ Network: 2.4 KB sent, 15.6 KB received

📝 [15:31:05] Agent activity:
   └─ Writing file: /output/analysis.json

⚠️ [15:31:08] Warning: High CPU usage
   ├─ Current: 92.3%
   ├─ Threshold: 90.0%
   └─ Action: Monitoring

📊 [15:31:10] Resource usage:
   ├─ CPU: 78.5%
   ├─ Memory: 445 MB / 1024 MB (43%)
   └─ Network: 5.2 KB sent, 28.1 KB received

✅ [15:31:15] Agent execution completed
   ├─ Exit Code: 0
   ├─ Duration: 23 seconds
   └─ Status: Success

📤 [15:31:16] Collecting output artifacts...
   ├─ File: analysis.json (4.2 KB)
   ├─ File: summary.txt (1.8 KB)
   └─ Total: 6.0 KB

🧹 [15:31:17] Cleaning up container...
   └─ Container abc123def456 removed

✅ [15:31:18] Sandbox session complete
   ├─ Total Duration: 33 seconds
   ├─ Exit Code: 0
   └─ Artifacts: 2 files (6.0 KB)
```

## Configuration

### Enable/Disable Telemetry

```python
from isolated_agents_sdk import run_agent, Policy

result = run_agent(
    agent=my_agent,
    working_dir="./workspace",
    policy=Policy(
        telemetry_enabled=True,  # Enable real-time telemetry (default: True)
        telemetry_level="INFO",  # DEBUG, INFO, WARNING, ERROR
        telemetry_format="rich",  # rich, simple, json
    ),
)
```

### Telemetry Levels

| Level | Events Shown |
|-------|-------------|
| **DEBUG** | All events including low-level operations |
| **INFO** | Standard events (lifecycle, metrics, activity) |
| **WARNING** | Warnings and errors only |
| **ERROR** | Errors only |

### Telemetry Formats

#### 1. Rich Format (Default)
- Color-coded output
- Emoji icons
- Tree-style formatting
- Progress indicators

```
🚀 [15:30:45] Starting agent...
   ├─ Container: abc123
   └─ Status: Running
```

#### 2. Simple Format
- Plain text output
- No colors or emojis
- Suitable for log files

```
[15:30:45] Starting agent...
  Container: abc123
  Status: Running
```

#### 3. JSON Format
- Structured JSON output
- Machine-readable
- Suitable for log aggregation

```json
{"timestamp": "15:30:45", "event": "agent_start", "container_id": "abc123", "status": "running"}
```

## Telemetry Events

### Lifecycle Events

```python
# Container provisioning
🚀 [timestamp] Provisioning container...
   ├─ Image: python:3.11-slim
   ├─ Container ID: abc123
   └─ Status: Running

# Agent execution start
🚀 [timestamp] Starting agent execution...
   └─ Command: python3 /tmp/_agent_bootstrap.py

# Agent execution complete
✅ [timestamp] Agent execution completed
   ├─ Exit Code: 0
   ├─ Duration: 23 seconds
   └─ Status: Success

# Container cleanup
🧹 [timestamp] Cleaning up container...
   └─ Container abc123 removed
```

### Resource Monitoring

```python
# Periodic resource updates (every 5 seconds by default)
📊 [timestamp] Resource usage:
   ├─ CPU: 45.8%
   ├─ Memory: 312 MB / 1024 MB (30%)
   └─ Network: 2.4 KB sent, 15.6 KB received

# High resource usage warning
⚠️ [timestamp] Warning: High CPU usage
   ├─ Current: 92.3%
   ├─ Threshold: 90.0%
   └─ Action: Monitoring

# OOM kill detection
❌ [timestamp] Error: Out of memory
   ├─ Memory Used: 1024 MB
   ├─ Memory Limit: 1024 MB
   └─ Action: Container terminated
```

### Agent Activity

```python
# File operations
📝 [timestamp] Agent activity:
   └─ Reading file: /workspace/data.csv

📝 [timestamp] Agent activity:
   └─ Writing file: /output/result.json

# Network requests
🌐 [timestamp] Network request:
   ├─ Destination: api.openai.com:443
   ├─ Method: POST
   └─ Status: Allowed

🌐 [timestamp] Network request blocked:
   ├─ Destination: malicious.com:80
   ├─ Reason: Not in allowed endpoints
   └─ Action: Denied
```

### Policy Violations

```python
# Filesystem access denied
❌ [timestamp] Policy violation: Filesystem access denied
   ├─ Path: /etc/passwd
   ├─ Reason: Outside allowed paths
   └─ Action: Access blocked

# Network connection denied
❌ [timestamp] Policy violation: Network connection denied
   ├─ Destination: unauthorized.com:443
   ├─ Reason: Not in allowed endpoints
   └─ Action: Connection blocked

# Timeout exceeded
⚠️ [timestamp] Warning: Timeout approaching
   ├─ Elapsed: 270 seconds
   ├─ Limit: 300 seconds
   └─ Remaining: 30 seconds

❌ [timestamp] Error: Timeout exceeded
   ├─ Elapsed: 300 seconds
   ├─ Limit: 300 seconds
   └─ Action: Agent terminated
```

### Dependency Installation

```python
# Installing pip packages
🔌 [timestamp] Installing dependencies...
   ├─ Package: langchain==0.1.0
   ├─ Package: langchain-openai==0.0.5
   └─ Status: Installing...

✅ [timestamp] Dependencies installed
   ├─ Packages: 2
   ├─ Size: 12.3 MB
   └─ Duration: 8 seconds

❌ [timestamp] Error: Dependency installation failed
   ├─ Package: invalid-package==1.0.0
   ├─ Error: Package not found
   └─ Action: Agent execution aborted
```

### Output Collection

```python
# Collecting artifacts
📤 [timestamp] Collecting output artifacts...
   ├─ Scanning: /output
   └─ Found: 3 files

📤 [timestamp] Artifact collected:
   ├─ File: analysis.json
   ├─ Size: 4.2 KB
   └─ Status: Copied to host

⚠️ [timestamp] Warning: Output size limit approaching
   ├─ Current: 9.5 MB
   ├─ Limit: 10.0 MB
   └─ Remaining: 0.5 MB

❌ [timestamp] Error: Output size limit exceeded
   ├─ Current: 10.5 MB
   ├─ Limit: 10.0 MB
   └─ Action: Collection aborted
```

## Implementation

### Telemetry Logger Class

```python
from isolated_agents_sdk.telemetry import TelemetryLogger

class TelemetryLogger:
    """Real-time telemetry logging for agent execution."""
    
    def __init__(
        self,
        enabled: bool = True,
        level: str = "INFO",
        format: str = "rich",
    ):
        self.enabled = enabled
        self.level = level
        self.format = format
    
    def log_lifecycle(self, event: str, details: dict):
        """Log lifecycle events (start, stop, etc.)"""
        if not self.enabled:
            return
        
        if self.format == "rich":
            self._log_rich(event, details, icon="🚀", color="blue")
        elif self.format == "simple":
            self._log_simple(event, details)
        elif self.format == "json":
            self._log_json(event, details)
    
    def log_metrics(self, metrics: dict):
        """Log resource usage metrics"""
        if not self.enabled or self.level == "ERROR":
            return
        
        if self.format == "rich":
            self._log_rich("Resource usage", metrics, icon="📊", color="cyan")
    
    def log_activity(self, activity: str, details: dict):
        """Log agent activity (file ops, network, etc.)"""
        if not self.enabled or self.level in ["WARNING", "ERROR"]:
            return
        
        if self.format == "rich":
            self._log_rich(activity, details, icon="📝", color="white")
    
    def log_warning(self, message: str, details: dict):
        """Log warnings"""
        if not self.enabled or self.level == "ERROR":
            return
        
        if self.format == "rich":
            self._log_rich(message, details, icon="⚠️", color="yellow")
    
    def log_error(self, message: str, details: dict):
        """Log errors"""
        if not self.enabled:
            return
        
        if self.format == "rich":
            self._log_rich(message, details, icon="❌", color="red")
    
    def log_success(self, message: str, details: dict):
        """Log success events"""
        if not self.enabled or self.level in ["WARNING", "ERROR"]:
            return
        
        if self.format == "rich":
            self._log_rich(message, details, icon="✅", color="green")
```

### Integration with Agent Runner

```python
# In agent_runner.py
class AgentRunner:
    def __init__(self, handle, audit_logger, telemetry_logger=None):
        self._handle = handle
        self._audit_logger = audit_logger
        self._telemetry = telemetry_logger or TelemetryLogger()
    
    async def run(self, agent, policy, session_id, agent_id):
        # Log agent start
        self._telemetry.log_lifecycle("Starting agent execution", {
            "agent_id": agent_id,
            "session_id": session_id,
            "container_id": self._handle.container_id,
        })
        
        # Install dependencies with progress
        if policy.pip_packages:
            self._telemetry.log_lifecycle("Installing dependencies", {
                "packages": policy.pip_packages,
            })
            await self._install_pip_packages(...)
            self._telemetry.log_success("Dependencies installed", {
                "count": len(policy.pip_packages),
            })
        
        # Execute agent
        proc = await asyncio.create_subprocess_exec(...)
        
        # Monitor resources in background
        asyncio.create_task(self._monitor_resources(session_id))
        
        # Stream output
        await self._stream_output(proc)
        
        exit_code = await proc.wait()
        
        # Log completion
        self._telemetry.log_success("Agent execution completed", {
            "exit_code": exit_code,
            "duration": elapsed_time,
        })
        
        return AgentResult(...)
    
    async def _monitor_resources(self, session_id):
        """Monitor and log resource usage"""
        while True:
            await asyncio.sleep(5)  # Every 5 seconds
            
            stats = await self._get_stats()
            
            self._telemetry.log_metrics({
                "cpu_percent": stats.cpu_percent,
                "memory_mb": stats.memory_mb,
                "memory_limit_mb": stats.memory_limit_mb,
            })
            
            # Check thresholds
            if stats.cpu_percent > 90:
                self._telemetry.log_warning("High CPU usage", {
                    "current": stats.cpu_percent,
                    "threshold": 90.0,
                })
```

## Advanced Features

### Progress Bars

For long-running operations, show progress bars:

```
🔌 Installing dependencies...
   ├─ langchain==0.1.0 ████████████████████ 100% (5.2 MB)
   ├─ langchain-openai ████████████░░░░░░░░  65% (3.1 MB)
   └─ Overall: ████████████████░░░░  80%
```

### Live Resource Dashboard

```
┌─ Resource Usage ────────────────────────────────────┐
│ CPU:    ████████████░░░░░░░░  45.8% / 100%         │
│ Memory: ████████░░░░░░░░░░░░  312 MB / 1024 MB     │
│ Network: ↑ 2.4 KB/s  ↓ 15.6 KB/s                   │
│ Disk:   ████░░░░░░░░░░░░░░░░  4.2 MB / 100 MB      │
└─────────────────────────────────────────────────────┘
```

### Event Timeline

```
Timeline:
├─ 00:00 🚀 Container provisioned
├─ 00:03 🔌 Dependencies installed
├─ 00:05 🚀 Agent started
├─ 00:08 📝 Reading data.csv
├─ 00:12 🌐 API call to openai.com
├─ 00:18 📝 Writing result.json
└─ 00:23 ✅ Agent completed
```

## Configuration Examples

### Minimal Output (Errors Only)

```python
policy = Policy(
    telemetry_enabled=True,
    telemetry_level="ERROR",
)
```

### Verbose Output (Debug Mode)

```python
policy = Policy(
    telemetry_enabled=True,
    telemetry_level="DEBUG",
    telemetry_format="rich",
)
```

### JSON Output (for Log Aggregation)

```python
policy = Policy(
    telemetry_enabled=True,
    telemetry_level="INFO",
    telemetry_format="json",
)
```

### Disable Telemetry

```python
policy = Policy(
    telemetry_enabled=False,
)
```

## Benefits

### For Users
- ✅ **Visibility** - See what agents are doing in real-time
- ✅ **Debugging** - Identify issues quickly
- ✅ **Transparency** - Understand agent behavior
- ✅ **Monitoring** - Track resource usage

### For Developers
- ✅ **Testing** - Verify agent behavior
- ✅ **Optimization** - Identify bottlenecks
- ✅ **Troubleshooting** - Debug issues faster
- ✅ **Validation** - Confirm policy enforcement

### For Operations
- ✅ **Monitoring** - Track agent performance
- ✅ **Alerting** - Detect anomalies
- ✅ **Auditing** - Compliance verification
- ✅ **Capacity Planning** - Resource usage trends

## Best Practices

1. **Use INFO level for production** - Balance between visibility and noise
2. **Use DEBUG level for development** - Maximum visibility for debugging
3. **Use JSON format for log aggregation** - Machine-readable for analysis
4. **Monitor resource metrics** - Detect performance issues early
5. **Review telemetry logs** - Understand agent behavior patterns

## Integration with Audit Logging

Telemetry logging complements audit logging:

- **Telemetry** - Real-time terminal output for users
- **Audit** - Persistent structured logs for compliance

Both systems work together to provide comprehensive visibility into agent operations.

---

**Telemetry logging makes the Isolated Agents SDK transparent and user-friendly by showing real-time agent activity in the terminal, helping users understand what their agents are doing inside the sandbox environment.**