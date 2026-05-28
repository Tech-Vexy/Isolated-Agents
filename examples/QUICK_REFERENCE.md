# Quick Reference Card

Fast reference for common patterns and commands.

## 🚀 Installation

```bash
# Install SDK
pip install isolated-agents-sdk

# Or with uv
uv pip install isolated-agents-sdk

# Verify container runtime
podman --version  # or docker --version
```

## 📝 Basic Agent Template

```python
from pathlib import Path
from isolated_agents_sdk import run_agent, Policy

def my_agent():
    """Agent function - imports must be inside."""
    from pathlib import Path
    
    # Your logic here
    result = "Hello from container!"
    
    # Write to /output
    output_dir = Path("/output")
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "result.txt").write_text(result)
    
    print(f"✓ Completed")
    return result

if __name__ == "__main__":
    output = Path("./output")
    output.mkdir(exist_ok=True)
    
    result = run_agent(
        agent=my_agent,
        working_dir="./workspace",
        host_output_path=output,
        policy=Policy(timeout_seconds=60)
    )
    
    print(f"Exit code: {result.exit_code}")
```

## 🔧 Policy Configuration

### Basic Policy
```python
Policy(
    cpu_cores=2.0,
    memory_mb=2048,
    timeout_seconds=120
)
```

### With Network Access
```python
Policy(
    network=NetworkPolicy(
        disabled=False,
        allowed_endpoints=["api.example.com:443"]
    ),
    allowed_env_vars=["API_KEY"],
    pip_packages=["requests"]
)
```

### With Database Access
```python
Policy(
    database_access={
        "main_db": {"type": "sql"}
    }
)
```

### Multi-Agent
```python
Policy(
    allow_sub_agents=True,
    memory_mb=2048
)
```

## 📂 File I/O Patterns

### Read Input
```python
# Inside agent function
from pathlib import Path

# Read from workspace
data = Path("/workspace/input.txt").read_text()
df = pd.read_csv("/workspace/data.csv")
```

### Write Output
```python
# Inside agent function
from pathlib import Path

output_dir = Path("/output")
output_dir.mkdir(parents=True, exist_ok=True)

# Write files
(output_dir / "result.txt").write_text(result)
(output_dir / "data.json").write_text(json.dumps(data))
```

## 🌐 Network Patterns

### HTTP Request
```python
def agent():
    import requests
    
    response = requests.get(
        "https://api.example.com/data",
        headers={"Authorization": f"Bearer {os.environ['API_KEY']}"},
        timeout=10
    )
    
    data = response.json()
```

### With Retry Logic
```python
def agent():
    import requests
    import time
    
    for attempt in range(3):
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            break
        except requests.RequestException:
            if attempt < 2:
                time.sleep(2 ** attempt)
            else:
                raise
```

## 🤖 LLM Integration

### OpenAI
```python
def agent():
    from langchain_openai import ChatOpenAI
    
    llm = ChatOpenAI(model="gpt-4")
    result = llm.invoke("Your prompt")
    
    Path("/output/response.txt").write_text(result.content)
```

### With Streaming
```python
def agent():
    from langchain_openai import ChatOpenAI
    
    llm = ChatOpenAI(model="gpt-4", streaming=True)
    
    for chunk in llm.stream("Your prompt"):
        print(chunk.content, end="", flush=True)
```

## 🔄 Multi-Agent Patterns

### Hierarchical (Manager-Worker)
```python
def manager():
    from isolated_agents_sdk.sub_agent_client import spawn_sub_agent
    
    result = spawn_sub_agent(
        agent=worker_function,
        kwargs={"task": "data"},
        policy=Policy(memory_mb=512)
    )
    
    return result.output

def worker_function(task):
    # Worker logic
    return f"Processed {task}"
```

### Sequential Pipeline
```python
# Run agents in sequence
result1 = run_agent(agent1, ...)
# Copy output to next workspace
shutil.copy(output / "result.txt", workspace / "input.txt")
result2 = run_agent(agent2, ...)
```

## 📊 Data Processing

### CSV Analysis
```python
def agent():
    import pandas as pd
    
    df = pd.read_csv("/workspace/data.csv")
    summary = df.describe()
    
    Path("/output/summary.txt").write_text(summary.to_string())
```

### Visualization
```python
def agent():
    import matplotlib.pyplot as plt
    import pandas as pd
    
    df = pd.read_csv("/workspace/data.csv")
    
    plt.figure(figsize=(10, 6))
    df.plot()
    plt.savefig("/output/plot.png", dpi=300)
```

## 🐛 Error Handling

### Basic Pattern
```python
def agent():
    try:
        result = risky_operation()
    except Exception as e:
        output_dir = Path("/output")
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "error.txt").write_text(str(e))
        raise
```

### With Logging
```python
def agent():
    print("Starting task...")
    
    try:
        print("✓ Step 1 completed")
        result = step1()
        
        print("✓ Step 2 completed")
        result = step2(result)
        
        print("✓ Task completed")
        return result
    except Exception as e:
        print(f"✗ Error: {e}")
        raise
```

## 🔍 Common Commands

### Run Example
```bash
python examples/example_name.py
```

### With Environment Variables
```bash
export OPENAI_API_KEY=sk-...
export API_KEY=your_key
python examples/example_name.py
```

### With Custom Input
```bash
python examples/example_name.py path/to/input.csv
```

### Check Container Runtime
```bash
podman ps        # List running containers
podman images    # List images
podman logs <id> # View container logs
```

## 📦 Common Packages

### Data Science
```python
pip_packages=[
    "pandas",
    "numpy",
    "matplotlib",
    "seaborn",
    "scikit-learn"
]
```

### Web & APIs
```python
pip_packages=[
    "requests",
    "beautifulsoup4",
    "httpx",
    "aiohttp"
]
```

### LLM Frameworks
```python
pip_packages=[
    "langchain",
    "langchain-openai",
    "crewai",
    "llama-index"
]
```

### Testing
```python
pip_packages=[
    "pytest",
    "hypothesis",
    "pytest-asyncio"
]
```

## ⚡ Performance Tips

### Resource Allocation
- **Light tasks**: 1 core, 512MB
- **Medium tasks**: 2 cores, 1-2GB
- **Heavy tasks**: 4 cores, 4GB+
- **Multi-agent**: 4+ cores, 2-4GB

### Timeout Guidelines
- **Simple queries**: 60s
- **Data processing**: 120-180s
- **Multi-agent**: 300-600s
- **Long-running**: 600s+

### Network Optimization
- Use connection pooling
- Implement retry logic
- Add rate limiting
- Cache responses

## 🚨 Troubleshooting

### "Container runtime not found"
```bash
# Install Podman
brew install podman  # macOS
sudo apt install podman  # Ubuntu

# Or Docker
# Download from docker.com
```

### "Import errors in agent"
- ✓ Imports must be **inside** agent function
- ✓ Add packages to `pip_packages` list
- ✗ Don't import at module level

### "Network access denied"
```python
# Enable network and specify endpoints
network=NetworkPolicy(
    disabled=False,
    allowed_endpoints=["api.example.com:443"]
)
```

### "Timeout errors"
```python
# Increase timeout
policy = Policy(
    timeout_seconds=300  # 5 minutes
)
```

### "Output files not created"
- ✓ Write to `/output` (not `./output`)
- ✓ Create directory first: `Path("/output").mkdir(parents=True, exist_ok=True)`
- ✓ Check `host_output_path` parameter

## 📚 Quick Links

- [Getting Started](GETTING_STARTED.md) - 5-minute guide
- [Examples Index](INDEX.md) - All examples
- [Scenarios](scenarios/) - Real-world use cases
- [Frameworks](frameworks/) - Framework integrations
- [Documentation](../docs/index.md) - Full docs

## 💡 Tips

1. **Start simple** - Begin with hello_world_agnostic.py
2. **Read examples** - Learn from working code
3. **Copy patterns** - Reuse proven patterns
4. **Test locally** - Verify before deploying
5. **Monitor resources** - Watch CPU/memory usage
6. **Handle errors** - Always add error handling
7. **Log progress** - Use print statements
8. **Restrict network** - Specify allowed endpoints
9. **Version packages** - Pin versions in production
10. **Read docs** - Check documentation when stuck

---

**Quick Start**: `pip install isolated-agents-sdk && python examples/hello_world_agnostic.py`
