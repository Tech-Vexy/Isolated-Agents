# Getting Started

Welcome to the Isolated Agents SDK! This guide will help you get up and running in minutes.

---

## Prerequisites

Before you begin, ensure you have:

- **Python 3.11 or higher**
- **Podman or Docker** installed
- **pip** or **uv** package manager

---

## Installation

### Using pip

```bash
pip install isolated-agents-sdk
```

### Using uv (recommended)

```bash
uv pip install isolated-agents-sdk
```

### From source

```bash
git clone https://github.com/isolated-agents/sdk
cd sdk
uv sync
```

---

## Container Runtime Setup

The SDK requires either Podman or Docker to be installed.

### Automatic Installation

The SDK can automatically install Podman for you:

```python
from isolated_agents_sdk.runtime_installer import RuntimeInstaller

installer = RuntimeInstaller()
if not installer.is_runtime_available():
    installer.install()  # Installs Podman automatically
```

### Manual Installation

=== "Linux"

    ```bash
    # Ubuntu/Debian
    sudo apt-get update
    sudo apt-get install -y podman
    
    # Fedora/RHEL
    sudo dnf install -y podman
    
    # Arch
    sudo pacman -S podman
    ```

=== "macOS"

    ```bash
    # Using Homebrew
    brew install podman
    
    # Initialize Podman machine
    podman machine init
    podman machine start
    ```

=== "Windows"

    ```powershell
    # Using WSL2
    wsl --install
    # Then install Podman in WSL2 using Linux instructions
    ```

See [Automatic Installation Guide](AUTOMATIC_INSTALLATION.md) for more details.

---

## Your First Agent

### Step 1: Create a Simple Agent

Create a file called `hello_agent.py`:

```python
from isolated_agents_sdk import run_agent, Policy

def hello_agent():
    """A simple agent that prints hello."""
    print("Hello from isolated container!")
    
    # Write output to file
    from pathlib import Path
    Path("/output/greeting.txt").write_text("Hello, World!")

# Run the agent
result = run_agent(
    agent=hello_agent,
    working_dir="./workspace",
    host_output_path="./output",
    policy=Policy()
)

print(f"Exit code: {result.exit_code}")
print(f"Output: {result.artifacts}")
```

### Step 2: Run It

```bash
python hello_agent.py
```

You should see:
```
Hello from isolated container!
Exit code: 0
Output: {'greeting.txt': './output/greeting.txt'}
```

---

## Your First AI Agent

### Step 1: Set Up API Key

```bash
export OPENAI_API_KEY=sk-...
```

### Step 2: Create an AI Agent

Create `ai_agent.py`:

```python
from isolated_agents_sdk import run_agent, Policy, NetworkPolicy
from pathlib import Path

def ai_agent():
    """AI agent using OpenAI."""
    from openai import OpenAI
    from pathlib import Path
    
    client = OpenAI()
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Explain quantum computing in 3 sentences."}
        ]
    )
    
    result = response.choices[0].message.content
    
    # Save output
    output_dir = Path("/output")
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "response.txt").write_text(result)
    
    print(f"Generated response: {len(result)} characters")

# Run with network access and API key
result = run_agent(
    agent=ai_agent,
    working_dir="./workspace",
    host_output_path="./output",
    policy=Policy(
        network=NetworkPolicy(
            disabled=False,
            allowed_endpoints=["api.openai.com:443"]
        ),
        allowed_env_vars=["OPENAI_API_KEY"],
        pip_packages=["openai"],
    )
)

# Read the response
response_path = result.artifacts["response.txt"]
print(f"\nResponse:\n{Path(response_path).read_text()}")
```

### Step 3: Run It

```bash
python ai_agent.py
```

---

## Understanding the Basics

### The `run_agent` Function

The main entry point for running agents:

```python
result = run_agent(
    agent=my_function,           # Your agent function
    working_dir="./workspace",   # Working directory (mapped to /workspace)
    host_output_path="./output", # Output directory (mapped to /output)
    policy=Policy(...)           # Security and resource policy
)
```

### The Policy Object

Controls security and resources:

```python
from isolated_agents_sdk import Policy, NetworkPolicy

policy = Policy(
    # Resources
    cpu_cores=2.0,
    memory_mb=1024,
    timeout_seconds=300,
    
    # Network
    network=NetworkPolicy(
        disabled=False,
        allowed_endpoints=["api.openai.com:443"]
    ),
    
    # Environment
    allowed_env_vars=["OPENAI_API_KEY"],
    
    # Dependencies
    pip_packages=["openai", "requests"],
)
```

### The AgentResult Object

Contains execution results:

```python
result = run_agent(...)

print(result.exit_code)      # 0 for success
print(result.session_id)     # Unique session ID
print(result.artifacts)      # Dict of output files
```

---

## Next Steps

### Learn Core Concepts

- [Architecture](concepts/architecture.md) - Understand the system design
- [Policies](concepts/policies.md) - Learn about security policies
- [Isolation](concepts/isolation.md) - How isolation works

### Explore Features

- [Decorators](DECORATORS.md) - Pythonic decorator API
- [Composability](COMPOSABILITY.md) - Chain agents together
- [Multimodal Outputs](MULTIMODAL_OUTPUTS.md) - Handle different output types

### Try Examples

- [Examples Catalog](EXAMPLES_CATALOG.md) - 81+ examples
- [LangChain Examples](examples/langchain.md) - LangChain integration
- [Multi-Agent Examples](examples/multi-agent.md) - Agent orchestration

### Read Guides

- [Best Practices](guides/best-practices.md) - Production patterns
- [Security](guides/security.md) - Security guidelines
- [Testing](guides/testing.md) - Testing strategies

---

## Common Patterns

### Pattern 1: Simple Agent

```python
def simple_agent():
    # Your logic here
    pass

result = run_agent(agent=simple_agent, policy=Policy())
```

### Pattern 2: Agent with Dependencies

```python
def agent_with_deps():
    import requests
    # Use requests...

result = run_agent(
    agent=agent_with_deps,
    policy=Policy(
        network=NetworkPolicy(disabled=False),
        pip_packages=["requests"]
    )
)
```

### Pattern 3: Agent with Files

```python
def file_processor():
    from pathlib import Path
    
    # Read from workspace
    data = Path("/workspace/input.txt").read_text()
    
    # Process...
    
    # Write to output
    Path("/output/result.txt").write_text(processed)

result = run_agent(
    agent=file_processor,
    working_dir="./data",
    host_output_path="./results",
    policy=Policy()
)
```

---

## Troubleshooting

### Container Runtime Not Found

```
Error: Podman/Docker not found
```

**Solution:** Install Podman or Docker, or use automatic installation:

```python
from isolated_agents_sdk.runtime_installer import RuntimeInstaller
RuntimeInstaller().install()
```

### Network Access Denied

```
Error: Network access denied
```

**Solution:** Enable network in policy:

```python
policy = Policy(
    network=NetworkPolicy(disabled=False)
)
```

### Import Errors

```
ModuleNotFoundError: No module named 'requests'
```

**Solution:** Add package to policy:

```python
policy = Policy(
    pip_packages=["requests"]
)
```

### Permission Denied

```
Error: Permission denied
```

**Solution:** Check file permissions or use rootless Podman.

See [Troubleshooting Guide](guides/troubleshooting.md) for more.

---

## Getting Help

- **Documentation**: [docs.isolated-agents.dev](https://docs.isolated-agents.dev)
- **GitHub Issues**: [github.com/isolated-agents/sdk/issues](https://github.com/isolated-agents/sdk/issues)
- **Discord**: [discord.gg/isolated-agents](https://discord.gg/isolated-agents)
- **Email**: support@isolated-agents.dev

---

## What's Next?

Now that you have the basics, explore:

1. **[Quick Start](quick-start.md)** - More detailed tutorial
2. **[Core Concepts](concepts/overview.md)** - Deep dive into concepts
3. **[Examples](EXAMPLES_CATALOG.md)** - Learn from examples
4. **[API Reference](api/overview.md)** - Complete API documentation

Happy coding! 🚀