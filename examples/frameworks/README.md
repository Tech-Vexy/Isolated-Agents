# Framework Integration Examples

Examples demonstrating how to use popular AI frameworks with the Isolated Agents SDK.

## Available Frameworks

### 🦜 LangChain
**Directory**: [`langchain/`](langchain/)

LangChain is a framework for developing applications powered by language models.

**Examples**:
- [`basic_agent.py`](langchain/basic_agent.py) - Simple LangChain agent with Groq/OpenAI
- [`rag_agent.py`](langchain/rag_agent.py) - RAG (Retrieval Augmented Generation) example

**Key Features**:
- Prompt templates
- Chain composition
- Multiple LLM providers (Groq, OpenAI)
- Output parsing

**Usage**:
```bash
# With Groq (free tier available)
export GROQ_API_KEY=gsk_...
python examples/frameworks/langchain/basic_agent.py

# Or with OpenAI
export OPENAI_API_KEY=sk-...
python examples/frameworks/langchain/basic_agent.py
```

---

### 🚢 CrewAI
**Directory**: [`crewai/`](crewai/)

CrewAI is a framework for orchestrating role-playing, autonomous AI agents.

**Examples**:
- [`basic_crew.py`](crewai/basic_crew.py) - Multi-agent content creation crew

**Key Features**:
- Role-based agents
- Sequential task execution
- Agent collaboration
- Autonomous decision-making

**Usage**:
```bash
export OPENAI_API_KEY=sk-...
python examples/frameworks/crewai/basic_crew.py
```

---

## Framework Comparison

| Framework | Best For | Complexity | Multi-Agent | Use Case |
|-----------|----------|------------|-------------|----------|
| LangChain | LLM chains, RAG | Low-Medium | No | Single-agent workflows |
| CrewAI | Role-based agents | Medium | Yes | Multi-agent collaboration |

## Common Patterns

### Pattern 1: LangChain Chain
```python
def langchain_agent():
    from langchain_openai import ChatOpenAI
    from langchain_core.prompts import ChatPromptTemplate
    
    llm = ChatOpenAI(model="gpt-4")
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are a helpful assistant."),
        ("user", "{input}")
    ])
    
    chain = prompt | llm
    result = chain.invoke({"input": "Your question"})
    
    # Save output
    Path("/output/response.txt").write_text(result.content)
```

### Pattern 2: CrewAI Crew
```python
def crewai_agent():
    from crewai import Agent, Task, Crew
    from langchain_openai import ChatOpenAI
    
    llm = ChatOpenAI(model="gpt-4")
    
    # Define agents
    researcher = Agent(
        role="Researcher",
        goal="Research topics",
        llm=llm
    )
    
    # Define tasks
    task = Task(
        description="Research AI safety",
        agent=researcher
    )
    
    # Create and run crew
    crew = Crew(agents=[researcher], tasks=[task])
    result = crew.kickoff()
    
    # Save output
    Path("/output/result.txt").write_text(str(result))
```

## Policy Configuration

### LangChain Policy
```python
policy = Policy(
    cpu_cores=2.0,
    memory_mb=1024,
    timeout_seconds=120,
    network=NetworkPolicy(
        disabled=False,
        allowed_endpoints=["api.openai.com:443"]
    ),
    allowed_env_vars=["OPENAI_API_KEY"],
    pip_packages=["langchain", "langchain-openai"]
)
```

### CrewAI Policy
```python
policy = Policy(
    cpu_cores=4.0,  # CrewAI needs more resources
    memory_mb=2048,
    timeout_seconds=600,  # Longer timeout for multi-agent
    network=NetworkPolicy(disabled=False),
    allowed_env_vars=["OPENAI_API_KEY"],
    pip_packages=["crewai", "langchain-openai"]
)
```

## API Keys

### Getting API Keys

**OpenAI**:
1. Sign up at https://platform.openai.com
2. Go to API Keys section
3. Create new secret key
4. Export: `export OPENAI_API_KEY=sk-...`

**Groq** (Free tier available):
1. Sign up at https://console.groq.com
2. Go to API Keys
3. Create new key
4. Export: `export GROQ_API_KEY=gsk_...`

**Anthropic**:
1. Sign up at https://console.anthropic.com
2. Go to API Keys
3. Create new key
4. Export: `export ANTHROPIC_API_KEY=sk-ant-...`

## Best Practices

### 1. Resource Allocation
- **LangChain**: 1-2 CPU cores, 1GB RAM
- **CrewAI**: 2-4 CPU cores, 2GB RAM (multi-agent)
- **RAG**: 2-4 CPU cores, 2-4GB RAM (vector operations)

### 2. Timeout Settings
- **Simple queries**: 60-120 seconds
- **Multi-agent**: 300-600 seconds
- **RAG with large docs**: 180-300 seconds

### 3. Network Policies
Always restrict to specific endpoints:
```python
network=NetworkPolicy(
    disabled=False,
    allowed_endpoints=[
        "api.openai.com:443",
        "api.groq.com:443"
    ]
)
```

### 4. Error Handling
```python
try:
    result = chain.invoke(input)
except Exception as e:
    # Save error for debugging
    Path("/output/error.txt").write_text(str(e))
    raise
```

## Troubleshooting

### Import Errors
**Problem**: `ModuleNotFoundError: No module named 'langchain'`

**Solution**: Packages are installed in container, not host. This is expected. Ensure packages are in `pip_packages` list.

### API Key Errors
**Problem**: `AuthenticationError: Invalid API key`

**Solution**: 
1. Check environment variable is set: `echo $OPENAI_API_KEY`
2. Ensure key is in `allowed_env_vars` list
3. Verify key is valid on provider's website

### Timeout Errors
**Problem**: Agent times out before completion

**Solution**: Increase `timeout_seconds` in policy:
```python
policy = Policy(
    timeout_seconds=600,  # 10 minutes
    ...
)
```

### Memory Errors
**Problem**: `MemoryError` or OOM kill

**Solution**: Increase memory allocation:
```python
policy = Policy(
    memory_mb=4096,  # 4GB
    ...
)
```

## Adding New Frameworks

To add a new framework (e.g., LlamaIndex, Haystack):

1. Create directory: `examples/frameworks/framework_name/`
2. Create basic example: `basic_agent.py`
3. Follow the template structure:
   - Docstring with description
   - Agent function with imports inside
   - Error handling
   - Output generation
   - Main block with policy
4. Add to this README
5. Test thoroughly

## Template

```python
"""Framework Name integration example.

This example demonstrates:
- Feature 1
- Feature 2

Usage:
    export API_KEY=...
    python examples/frameworks/framework_name/basic_agent.py
"""

import os
import sys
from pathlib import Path


def framework_agent():
    """Agent using Framework Name."""
    from framework_name import SomeClass
    from pathlib import Path
    
    # Your framework logic
    result = SomeClass().do_something()
    
    # Save output
    output_dir = Path("/output")
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "result.txt").write_text(str(result))
    
    print("✓ Completed")


if __name__ == "__main__":
    from isolated_agents_sdk import run_agent, Policy, NetworkPolicy
    
    if not os.environ.get("API_KEY"):
        print("Error: API_KEY not set", file=sys.stderr)
        sys.exit(1)
    
    output = Path("./output")
    output.mkdir(exist_ok=True)
    
    result = run_agent(
        agent=framework_agent,
        working_dir="./workspace",
        host_output_path=output,
        policy=Policy(
            cpu_cores=2.0,
            memory_mb=2048,
            network=NetworkPolicy(disabled=False),
            allowed_env_vars=["API_KEY"],
            pip_packages=["framework-name"]
        )
    )
    
    sys.exit(result.exit_code)
```

## Related Examples

- [Scenario Examples](../scenarios/) - Real-world use cases
- [Advanced Examples](../advanced/) - Complex patterns
- [Distributed Examples](../distributed/) - Multi-agent systems

## Resources

- [LangChain Documentation](https://python.langchain.com/docs/get_started/introduction)
- [CrewAI Documentation](https://docs.crewai.com/)
- [Isolated Agents SDK Documentation](../../docs/index.md)

---

**Last Updated**: May 28, 2026
