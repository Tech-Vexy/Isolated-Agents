# Quick Start Guide

Get up and running with Isolated Agents SDK in 5 minutes!

---

## Step 1: Install

```bash
pip install isolated-agents-sdk
```

---

## Step 2: Verify Installation

```bash
python -c "import isolated_agents_sdk; print(isolated_agents_sdk.__version__)"
```

---

## Step 3: Your First Agent

Create `hello.py`:

```python
from isolated_agents_sdk import run_agent, Policy
from pathlib import Path

def hello_agent():
    """Simple hello world agent."""
    print("Hello from isolated container!")
    Path("/output/greeting.txt").write_text("Hello, World!")

result = run_agent(
    agent=hello_agent,
    working_dir="./workspace",
    host_output_path="./output",
    policy=Policy()
)

print(f"✓ Agent completed with exit code {result.exit_code}")
print(f"✓ Output: {Path(result.artifacts['greeting.txt']).read_text()}")
```

Run it:

```bash
python hello.py
```

---

## Step 4: Add AI Capabilities

Create `ai_agent.py`:

```python
from isolated_agents_sdk import run_agent, Policy, NetworkPolicy
from pathlib import Path
import os

def ai_agent():
    """AI agent using OpenAI."""
    from openai import OpenAI
    from pathlib import Path
    
    client = OpenAI()
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {"role": "user", "content": "Explain AI in 3 sentences"}
        ]
    )
    
    result = response.choices[0].message.content
    Path("/output/response.txt").write_text(result)
    print(f"✓ Generated {len(result)} characters")

# Set API key
os.environ["OPENAI_API_KEY"] = "sk-..."

# Run agent
result = run_agent(
    agent=ai_agent,
    working_dir="./workspace",
    host_output_path="./output",
    policy=Policy(
        network=NetworkPolicy(disabled=False),
        allowed_env_vars=["OPENAI_API_KEY"],
        pip_packages=["openai"],
    )
)

print(f"\n{Path(result.artifacts['response.txt']).read_text()}")
```

---

## Step 5: Explore Examples

Browse [81+ examples](EXAMPLES_CATALOG.md) for:

- **LangChain** - RAG, chains, agents
- **CrewAI** - Multi-agent systems
- **Data Analysis** - Pandas, visualization
- **Web Scraping** - Requests, BeautifulSoup
- **Code Generation** - AI-powered coding

---

## Next Steps

- [Getting Started Guide](getting-started.md) - Detailed tutorial
- [Architecture](ADAPTER_ARCHITECTURE.md) - Understand the architecture
- [Examples](EXAMPLES_CATALOG.md) - Learn from examples
- [Implementation Guide](COMPLETE_IMPLEMENTATION_GUIDE.md) - Detailed technical guide

---

## Common Commands

```bash
# Install SDK
pip install isolated-agents-sdk

# Run agent
python my_agent.py

# Build documentation
mkdocs serve

# Run tests
pytest tests/
```

---

## Need Help?

- **Docs**: [docs.isolated-agents.dev](https://docs.isolated-agents.dev)
- **GitHub**: [github.com/Tech-Vexy/Isolated-Agents](https://github.com/Tech-Vexy/Isolated-Agents)
- **Discord**: [discord.gg/isolated-agents](https://discord.gg/isolated-agents)