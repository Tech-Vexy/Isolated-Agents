# Getting Started with Isolated Agents SDK

Welcome! This guide will help you get started with the Isolated Agents SDK through practical examples.

## Quick Start (5 minutes)

### 1. Installation

```bash
# Install the SDK
pip install isolated-agents-sdk

# Or with uv (recommended)
uv pip install isolated-agents-sdk
```

### 2. Verify Container Runtime

The SDK requires either Podman or Docker:

```bash
# Check if Podman is installed
podman --version

# Or check for Docker
docker --version
```

If neither is installed, see [Container Runtime Setup](#container-runtime-setup) below.

### 3. Your First Agent

Create a file `hello_agent.py`:

```python
"""Your first isolated agent."""

from pathlib import Path
from isolated_agents_sdk import run_agent, Policy

def my_first_agent():
    """This function runs inside an isolated container."""
    from pathlib import Path
    
    # Your agent logic here
    message = "Hello from inside a secure container!"
    
    # Write output to /output directory
    output_dir = Path("/output")
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "greeting.txt").write_text(message)
    
    print(f"✓ {message}")
    return message

if __name__ == "__main__":
    # Create output directory on host
    output = Path("./output")
    output.mkdir(exist_ok=True)
    
    print("Launching your first agent...")
    
    # Run the agent in an isolated container
    result = run_agent(
        agent=my_first_agent,
        working_dir="./workspace",
        host_output_path=output,
        policy=Policy(timeout_seconds=60)
    )
    
    print(f"\n✓ Agent completed with exit code {result.exit_code}")
    
    # Read the output
    if result.artifacts.get("greeting.txt"):
        greeting = Path(result.artifacts["greeting.txt"]).read_text()
        print(f"Agent says: {greeting}")
```

Run it:

```bash
python hello_agent.py
```

**What just happened?**
- Your function was serialized and sent to a container
- It ran in complete isolation (separate filesystem, network, processes)
- Output was safely extracted back to your host machine
- The container was automatically cleaned up

## Core Concepts

### 1. Agent Functions

Agent functions are regular Python functions that run inside containers:

```python
def my_agent():
    """Import dependencies inside the function."""
    import requests  # Imports must be inside
    from pathlib import Path
    
    # Your logic here
    data = requests.get("https://api.example.com/data").json()
    
    # Write outputs to /output
    Path("/output/result.json").write_text(str(data))
```

**Key Rules:**
- ✓ Import dependencies **inside** the function
- ✓ Write outputs to `/output` directory
- ✓ Read inputs from `/workspace` directory
- ✗ Don't rely on global variables from host

### 2. Policies

Policies control what your agent can do:

```python
from isolated_agents_sdk import Policy, NetworkPolicy

policy = Policy(
    # Resource limits
    cpu_cores=2.0,
    memory_mb=2048,
    timeout_seconds=300,
    
    # Network access
    network=NetworkPolicy(
        disabled=False,  # Enable network
        allowed_endpoints=["api.openai.com:443"]
    ),
    
    # Environment variables
    allowed_env_vars=["OPENAI_API_KEY", "API_TOKEN"],
    
    # Python packages
    pip_packages=["requests", "pandas", "numpy"]
)
```

### 3. Working Directory & Output

```python
# Host filesystem structure:
project/
├── workspace/          # Input files (mounted read-only in container)
│   └── data.csv
├── output/            # Output files (written by agent)
│   └── results.txt
└── my_agent.py

# Inside container:
/workspace/data.csv    # Read input files here
/output/results.txt    # Write output files here
```

## Common Patterns

### Pattern 1: API Integration

```python
"""Call an external API safely."""

import os
from pathlib import Path
from isolated_agents_sdk import run_agent, Policy, NetworkPolicy

def api_agent():
    """Fetch data from an API."""
    import requests
    from pathlib import Path
    
    api_key = os.environ.get("API_KEY")
    response = requests.get(
        "https://api.example.com/data",
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=10
    )
    
    data = response.json()
    
    # Save result
    output_dir = Path("/output")
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "api_response.json").write_text(str(data))
    
    print(f"✓ Fetched {len(data)} items")

if __name__ == "__main__":
    result = run_agent(
        agent=api_agent,
        working_dir="./workspace",
        host_output_path=Path("./output"),
        policy=Policy(
            network=NetworkPolicy(
                disabled=False,
                allowed_endpoints=["api.example.com:443"]
            ),
            allowed_env_vars=["API_KEY"],
            pip_packages=["requests"]
        )
    )
```

### Pattern 2: Data Processing

```python
"""Process data files safely."""

from pathlib import Path
from isolated_agents_sdk import run_agent, Policy

def data_processor():
    """Process CSV data."""
    import pandas as pd
    from pathlib import Path
    
    # Read input from workspace
    df = pd.read_csv("/workspace/input.csv")
    
    # Process data
    summary = df.describe()
    filtered = df[df['value'] > 100]
    
    # Write outputs
    output_dir = Path("/output")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    (output_dir / "summary.txt").write_text(summary.to_string())
    filtered.to_csv(output_dir / "filtered.csv", index=False)
    
    print(f"✓ Processed {len(df)} rows, filtered to {len(filtered)}")

if __name__ == "__main__":
    # Prepare input data
    workspace = Path("./workspace")
    workspace.mkdir(exist_ok=True)
    
    # Create sample data
    import pandas as pd
    sample_data = pd.DataFrame({
        'id': range(1, 101),
        'value': [i * 10 for i in range(1, 101)]
    })
    sample_data.to_csv(workspace / "input.csv", index=False)
    
    # Run agent
    result = run_agent(
        agent=data_processor,
        working_dir=workspace,
        host_output_path=Path("./output"),
        policy=Policy(
            memory_mb=2048,
            pip_packages=["pandas"]
        )
    )
```

### Pattern 3: LLM Integration

```python
"""Use LLMs safely with network isolation."""

import os
from pathlib import Path
from isolated_agents_sdk import run_agent, Policy, NetworkPolicy

def llm_agent():
    """Generate content with an LLM."""
    from langchain_openai import ChatOpenAI
    from pathlib import Path
    
    llm = ChatOpenAI(model="gpt-4")
    
    prompt = "Explain quantum computing in simple terms"
    response = llm.invoke(prompt)
    
    # Save output
    output_dir = Path("/output")
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "response.txt").write_text(response.content)
    
    print(f"✓ Generated {len(response.content)} characters")

if __name__ == "__main__":
    if not os.environ.get("OPENAI_API_KEY"):
        print("Error: OPENAI_API_KEY not set")
        exit(1)
    
    result = run_agent(
        agent=llm_agent,
        working_dir="./workspace",
        host_output_path=Path("./output"),
        policy=Policy(
            network=NetworkPolicy(disabled=False),
            allowed_env_vars=["OPENAI_API_KEY"],
            pip_packages=["langchain-openai"]
        )
    )
```

## Next Steps

### Beginner Examples
1. [Hello World](hello_world_agnostic.py) - Basic agent execution
2. [File Processing](file_summariser_agnostic.py) - Read and write files
3. [API Integration](scenarios/api_integration/rest_api_agent.py) - Call external APIs

### Intermediate Examples
1. [Multi-Agent Pipeline](multi_agent_hierarchy.py) - Chain multiple agents
2. [Web Scraping](scenarios/web_scraping/scrape_and_analyze.py) - Scrape and analyze websites
3. [Data Analysis](scenarios/data_analysis/csv_analysis.py) - Process and visualize data

### Advanced Examples
1. [Distributed Agents](distributed/) - Multi-agent communication
2. [Server Agents](advanced/server_agent.py) - Long-running services
3. [Recursive Agents](advanced/recursive_agent.py) - Agents spawning sub-agents

### Framework-Specific Examples
- [LangChain](frameworks/langchain/) - LangChain integration
- [CrewAI](frameworks/crewai/) - CrewAI integration
- [LlamaIndex](frameworks/llamaindex/) - LlamaIndex integration

## Container Runtime Setup

### Podman (Recommended)

**Linux:**
```bash
# Ubuntu/Debian
sudo apt-get install podman

# Fedora
sudo dnf install podman

# Arch
sudo pacman -S podman
```

**macOS:**
```bash
brew install podman
podman machine init
podman machine start
```

**Windows:**
```powershell
# Install via Chocolatey
choco install podman

# Or download from: https://podman.io/getting-started/installation
```

### Docker

**Linux:**
```bash
# Ubuntu/Debian
curl -fsSL https://get.docker.com | sh

# Add user to docker group
sudo usermod -aG docker $USER
```

**macOS/Windows:**
Download Docker Desktop from https://www.docker.com/products/docker-desktop

## Troubleshooting

### "Container runtime not found"
- Install Podman or Docker (see above)
- Verify installation: `podman --version` or `docker --version`

### "Permission denied"
- Linux: Add user to docker group: `sudo usermod -aG docker $USER`
- Then log out and back in

### "Import errors in agent"
- Ensure packages are listed in `pip_packages` policy parameter
- Imports must be **inside** the agent function

### "Network access denied"
- Set `network=NetworkPolicy(disabled=False)` in policy
- Add required endpoints to `allowed_endpoints`

### "Output files not created"
- Ensure agent writes to `/output` directory (not `./output`)
- Check `host_output_path` parameter is set correctly

### "Timeout errors"
- Increase `timeout_seconds` in policy
- Check if agent is stuck in infinite loop

## Best Practices

### ✓ Do's
- Import dependencies inside agent functions
- Write outputs to `/output` directory
- Use specific package versions in production
- Set appropriate resource limits
- Use network policies to restrict access
- Handle errors gracefully
- Log progress with print statements

### ✗ Don'ts
- Don't rely on global variables from host
- Don't hardcode credentials (use environment variables)
- Don't write to arbitrary filesystem locations
- Don't use `network=NetworkPolicy(disabled=False)` without `allowed_endpoints` in production
- Don't ignore exit codes and errors

## Getting Help

- **Documentation**: [Full Documentation](../docs/index.md)
- **Examples**: Browse the [examples/](.) directory
- **Issues**: [GitHub Issues](https://github.com/Tech-Vexy/Isolated-Agents/issues)
- **Discussions**: [GitHub Discussions](https://github.com/Tech-Vexy/Isolated-Agents/discussions)

## What's Next?

Now that you understand the basics, explore:

1. **[ALL_EXAMPLES.md](ALL_EXAMPLES.md)** - Complete example collection
2. **[README.md](README.md)** - Full examples catalog
3. **[Advanced Examples](advanced/)** - Complex patterns
4. **[Framework Examples](frameworks/)** - Framework integrations

Happy coding! 🚀
