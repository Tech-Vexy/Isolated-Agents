# Troubleshooting Guide

Comprehensive solutions to common issues when using the Isolated Agents SDK.

## 🔍 Quick Diagnosis

### Is your issue here?
- [Container Runtime Issues](#container-runtime-issues)
- [Import and Package Errors](#import-and-package-errors)
- [Network and API Errors](#network-and-api-errors)
- [File I/O Issues](#file-io-issues)
- [Resource and Performance Issues](#resource-and-performance-issues)
- [Multi-Agent Issues](#multi-agent-issues)
- [Framework-Specific Issues](#framework-specific-issues)

---

## Container Runtime Issues

### ❌ "Container runtime not found"

**Error Message**:
```
RuntimeError: No container runtime found. Install Podman or Docker.
```

**Cause**: Neither Podman nor Docker is installed or not in PATH.

**Solution**:

**Linux (Ubuntu/Debian)**:
```bash
# Install Podman (recommended)
sudo apt-get update
sudo apt-get install podman

# Or Docker
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
# Log out and back in
```

**macOS**:
```bash
# Install Podman
brew install podman
podman machine init
podman machine start

# Or Docker Desktop
# Download from https://www.docker.com/products/docker-desktop
```

**Windows**:
```powershell
# Install Podman
choco install podman

# Or Docker Desktop
# Download from https://www.docker.com/products/docker-desktop
```

**Verify Installation**:
```bash
podman --version  # or docker --version
```

---

### ❌ "Permission denied" (Linux/Docker)

**Error Message**:
```
PermissionError: Got permission denied while trying to connect to the Docker daemon socket
```

**Cause**: User not in docker group.

**Solution**:
```bash
# Add user to docker group
sudo usermod -aG docker $USER

# Log out and back in, or run:
newgrp docker

# Verify
docker ps
```

---

### ❌ "Podman machine not running" (macOS)

**Error Message**:
```
Error: cannot connect to Podman. Is the podman machine running?
```

**Solution**:
```bash
# Start Podman machine
podman machine start

# Check status
podman machine list

# If issues persist, recreate machine
podman machine stop
podman machine rm
podman machine init
podman machine start
```

---

## Import and Package Errors

### ❌ "ModuleNotFoundError" in agent

**Error Message**:
```python
ModuleNotFoundError: No module named 'requests'
```

**Cause**: Package not installed in container.

**Solution**:

✅ **Correct** - Add to pip_packages:
```python
policy = Policy(
    pip_packages=["requests", "pandas", "numpy"]
)
```

✅ **Correct** - Import inside agent function:
```python
def my_agent():
    import requests  # ✓ Inside function
    from pathlib import Path
    
    response = requests.get("https://api.example.com")
```

❌ **Wrong** - Import at module level:
```python
import requests  # ✗ Outside function

def my_agent():
    response = requests.get("https://api.example.com")
```

---

### ❌ "Import errors on host"

**Error Message**:
```python
ImportError: cannot import name 'ChatOpenAI' from 'langchain_openai'
```

**Cause**: This is **expected behavior**. Packages are installed in container, not host.

**Solution**: This is not an error! The code will work when run in the container. The host doesn't need these packages.

**Verification**:
```python
# This is normal - host doesn't have langchain
from langchain_openai import ChatOpenAI  # ImportError on host

# But this works - runs in container
def agent():
    from langchain_openai import ChatOpenAI  # ✓ Works in container
    llm = ChatOpenAI(model="gpt-4")
```

---

### ❌ "Package version conflicts"

**Error Message**:
```
ERROR: pip's dependency resolver does not currently take into account all the packages that are installed
```

**Solution**: Pin specific versions:
```python
policy = Policy(
    pip_packages=[
        "langchain==0.3.7",
        "langchain-openai==0.2.0",
        "pydantic==2.5.0"
    ]
)
```

---

## Network and API Errors

### ❌ "Network access denied"

**Error Message**:
```
requests.exceptions.ConnectionError: Network is unreachable
```

**Cause**: Network is disabled or endpoint not allowed.

**Solution**:

✅ **Enable network and specify endpoints**:
```python
policy = Policy(
    network=NetworkPolicy(
        disabled=False,  # Must be False
        allowed_endpoints=[
            "api.openai.com:443",
            "api.example.com:443"
        ]
    )
)
```

❌ **Wrong** - Network disabled:
```python
policy = Policy(
    network=NetworkPolicy(disabled=True)  # ✗ Network blocked
)
```

---

### ❌ "API authentication failed"

**Error Message**:
```
AuthenticationError: Invalid API key provided
```

**Cause**: API key not set or not passed to container.

**Solution**:

1. **Set environment variable**:
```bash
export OPENAI_API_KEY=sk-...
export GROQ_API_KEY=gsk_...
```

2. **Add to allowed_env_vars**:
```python
policy = Policy(
    allowed_env_vars=["OPENAI_API_KEY", "GROQ_API_KEY"]
)
```

3. **Verify it's set**:
```bash
echo $OPENAI_API_KEY  # Should show your key
```

---

### ❌ "SSL certificate verification failed"

**Error Message**:
```
SSLError: [SSL: CERTIFICATE_VERIFY_FAILED]
```

**Solution**:

**Option 1** - Update certificates (recommended):
```bash
# Ubuntu/Debian
sudo apt-get install ca-certificates

# macOS
brew install ca-certificates
```

**Option 2** - Disable verification (not recommended for production):
```python
def agent():
    import requests
    response = requests.get(url, verify=False)
```

---

### ❌ "Connection timeout"

**Error Message**:
```
requests.exceptions.Timeout: HTTPSConnectionPool: Read timed out
```

**Solution**: Increase timeout and add retry logic:
```python
def agent():
    import requests
    import time
    
    for attempt in range(3):
        try:
            response = requests.get(
                url,
                timeout=30,  # Increase timeout
                headers={"User-Agent": "MyAgent/1.0"}
            )
            response.raise_for_status()
            break
        except requests.Timeout:
            if attempt < 2:
                wait = 2 ** attempt
                print(f"Timeout, retrying in {wait}s...")
                time.sleep(wait)
            else:
                raise
```

---

## File I/O Issues

### ❌ "Output files not created"

**Error Message**:
```
FileNotFoundError: [Errno 2] No such file or directory: './output/result.txt'
```

**Cause**: Writing to wrong path or directory not created.

**Solution**:

✅ **Correct** - Write to /output:
```python
def agent():
    from pathlib import Path
    
    output_dir = Path("/output")  # ✓ Absolute path
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "result.txt").write_text("data")
```

❌ **Wrong** - Relative path:
```python
def agent():
    Path("./output/result.txt").write_text("data")  # ✗ Wrong path
```

---

### ❌ "Input files not found"

**Error Message**:
```
FileNotFoundError: [Errno 2] No such file or directory: '/workspace/input.csv'
```

**Cause**: File not in workspace directory on host.

**Solution**:

1. **Create workspace and add files**:
```python
workspace = Path("./workspace")
workspace.mkdir(exist_ok=True)

# Copy your input file
import shutil
shutil.copy("data.csv", workspace / "data.csv")
```

2. **Read from /workspace in agent**:
```python
def agent():
    import pandas as pd
    df = pd.read_csv("/workspace/data.csv")  # ✓ Correct
```

---

### ❌ "Permission denied writing files"

**Error Message**:
```
PermissionError: [Errno 13] Permission denied: '/output/result.txt'
```

**Solution**:

1. **Ensure output directory is writable**:
```bash
chmod 755 ./output
```

2. **Create directory with proper permissions**:
```python
output = Path("./output")
output.mkdir(exist_ok=True, mode=0o755)
```

---

## Resource and Performance Issues

### ❌ "Agent timeout"

**Error Message**:
```
TimeoutError: Agent execution exceeded timeout of 60 seconds
```

**Cause**: Agent takes longer than timeout setting.

**Solution**: Increase timeout:
```python
policy = Policy(
    timeout_seconds=300  # 5 minutes
)
```

**Guidelines**:
- Simple queries: 60-120s
- Data processing: 120-300s
- Multi-agent: 300-600s
- Long-running: 600s+

---

### ❌ "Out of memory" / OOM killed

**Error Message**:
```
MemoryError: Unable to allocate array
# Or container exits with code 137
```

**Cause**: Agent exceeds memory limit.

**Solution**: Increase memory:
```python
policy = Policy(
    memory_mb=4096  # 4GB
)
```

**Memory Guidelines**:
- Light tasks: 512MB - 1GB
- Medium tasks: 1-2GB
- Heavy data processing: 2-4GB
- Multi-agent: 2-4GB+

**Optimization**:
```python
def agent():
    import pandas as pd
    
    # Process in chunks for large files
    for chunk in pd.read_csv("large.csv", chunksize=10000):
        process(chunk)
```

---

### ❌ "CPU throttling / slow performance"

**Cause**: Insufficient CPU allocation.

**Solution**: Increase CPU cores:
```python
policy = Policy(
    cpu_cores=4.0  # 4 cores
)
```

**CPU Guidelines**:
- Light tasks: 1 core
- Medium tasks: 2 cores
- Heavy computation: 4+ cores
- Multi-agent: 4+ cores

---

## Multi-Agent Issues

### ❌ "Sub-agent spawn failed"

**Error Message**:
```
RuntimeError: Sub-agent spawning not allowed
```

**Cause**: `allow_sub_agents` not enabled.

**Solution**:
```python
policy = Policy(
    allow_sub_agents=True,  # Must enable
    memory_mb=2048  # Parent needs enough memory
)
```

---

### ❌ "Resource budget exceeded"

**Error Message**:
```
ResourceError: Sub-agent memory request exceeds parent budget
```

**Cause**: Sub-agent requests more resources than parent has.

**Solution**: Ensure parent has enough resources:
```python
# Parent policy
parent_policy = Policy(
    allow_sub_agents=True,
    memory_mb=2048  # Parent gets 2GB
)

# Sub-agent can use up to parent's remaining budget
def manager():
    from isolated_agents_sdk.sub_agent_client import spawn_sub_agent
    
    result = spawn_sub_agent(
        agent=worker,
        policy=Policy(memory_mb=512)  # Worker gets 512MB
    )
```

---

### ❌ "IPC communication failed"

**Error Message**:
```
IPCError: Failed to communicate with host daemon
```

**Cause**: IPC daemon not running or connection lost.

**Solution**:

1. **Ensure runtime is started**:
```python
runtime = AgentRuntime(working_dir="./workspace")
await runtime.start()  # Must start runtime

try:
    result = await runtime.run_agent(agent, policy=policy)
finally:
    await runtime.stop()  # Clean shutdown
```

2. **Check for port conflicts**:
```python
# Use different port if default is taken
runtime = AgentRuntime(
    working_dir="./workspace",
    ipc_port=9001  # Default is 9000
)
```

---

## Framework-Specific Issues

### LangChain Issues

#### ❌ "Pydantic validation error"

**Error Message**:
```
ValidationError: 1 validation error for ChatOpenAI
```

**Solution**: Pin compatible versions:
```python
policy = Policy(
    pip_packages=[
        "langchain==0.3.7",
        "langchain-openai==0.2.0",
        "pydantic==2.5.0"
    ]
)
```

---

### CrewAI Issues

#### ❌ "CrewAI timeout"

**Cause**: CrewAI multi-agent execution takes longer.

**Solution**: Increase timeout and resources:
```python
policy = Policy(
    cpu_cores=4.0,
    memory_mb=2048,
    timeout_seconds=600  # 10 minutes
)
```

---

## Debugging Tips

### Enable Verbose Logging

```python
import logging
from isolated_agents_sdk import setup_logging

setup_logging(level=logging.DEBUG, structured=False)
```

### Check Container Logs

```bash
# List containers
podman ps -a

# View logs
podman logs <container_id>

# Follow logs in real-time
podman logs -f <container_id>
```

### Inspect Container

```bash
# Get container details
podman inspect <container_id>

# Execute command in container
podman exec -it <container_id> /bin/bash
```

### Test Locally First

```python
# Test your agent function locally before containerizing
def my_agent():
    # Your logic
    pass

# Test it
result = my_agent()
print(result)

# Then containerize
result = run_agent(agent=my_agent, ...)
```

### Use Print Statements

```python
def agent():
    print("Starting agent...")
    print(f"✓ Step 1 completed")
    print(f"✓ Step 2 completed")
    print(f"✓ Agent completed")
```

### Save Debug Information

```python
def agent():
    import sys
    import os
    from pathlib import Path
    
    try:
        # Your logic
        result = do_something()
    except Exception as e:
        # Save debug info
        debug_info = f"""
Error: {str(e)}
Type: {type(e).__name__}
Python: {sys.version}
CWD: {os.getcwd()}
Files: {list(Path('.').glob('*'))}
"""
        Path("/output/debug.txt").write_text(debug_info)
        raise
```

---

## Getting Help

### Before Asking for Help

1. ✅ Check this troubleshooting guide
2. ✅ Read the error message carefully
3. ✅ Check [Getting Started](GETTING_STARTED.md)
4. ✅ Review relevant examples
5. ✅ Enable debug logging
6. ✅ Check container logs

### Where to Get Help

- **Documentation**: [Full Docs](../docs/index.md)
- **Examples**: [Examples Index](INDEX.md)
- **GitHub Issues**: [Report Bug](https://github.com/Tech-Vexy/Isolated-Agents/issues)
- **Discussions**: [Ask Question](https://github.com/Tech-Vexy/Isolated-Agents/discussions)

### When Reporting Issues

Include:
1. Error message (full traceback)
2. Minimal reproducible example
3. SDK version: `pip show isolated-agents-sdk`
4. Container runtime: `podman --version` or `docker --version`
5. OS and Python version
6. What you've tried

---

## Common Gotchas

### ❌ Imports at module level
```python
import requests  # ✗ Wrong

def agent():
    import requests  # ✓ Correct
```

### ❌ Relative paths
```python
Path("./output/file.txt")  # ✗ Wrong
Path("/output/file.txt")   # ✓ Correct
```

### ❌ Forgetting to create output directory
```python
Path("/output/file.txt").write_text("data")  # ✗ May fail

output_dir = Path("/output")
output_dir.mkdir(parents=True, exist_ok=True)  # ✓ Correct
(output_dir / "file.txt").write_text("data")
```

### ❌ Not handling errors
```python
result = risky_operation()  # ✗ No error handling

try:  # ✓ Correct
    result = risky_operation()
except Exception as e:
    Path("/output/error.txt").write_text(str(e))
    raise
```

### ❌ Hardcoding credentials
```python
api_key = "sk-..."  # ✗ Hardcoded

api_key = os.environ["API_KEY"]  # ✓ From environment
```

---

**Still stuck?** Open an issue on [GitHub](https://github.com/Tech-Vexy/Isolated-Agents/issues) with details!
