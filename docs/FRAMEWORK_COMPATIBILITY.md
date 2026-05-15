# Framework Compatibility Guide - Universal Local Sandbox

## Overview

The Isolated Agents SDK is designed as a **framework-agnostic local sandbox** that works with ANY agent framework. It provides secure, isolated execution environments for agents regardless of their underlying implementation (LangChain, AutoGPT, CrewAI, custom frameworks, etc.).

## Core Principle: Framework Agnosticism

The SDK achieves universal compatibility through two key mechanisms:

1. **Python Callable Injection** - Serialize any Python function and execute it in isolation
2. **Entrypoint Mode** - Execute any command/script in any language (Python, Node.js, Go, etc.)

## Compatibility Matrix

| Framework | Compatibility | Integration Method | Example |
|-----------|--------------|-------------------|---------|
| **LangChain** | ✅ Full | Python Callable | [See below](#langchain) |
| **AutoGPT** | ✅ Full | Entrypoint Mode | [See below](#autogpt) |
| **CrewAI** | ✅ Full | Python Callable | [See below](#crewai) |
| **Semantic Kernel** | ✅ Full | Entrypoint Mode | [See below](#semantic-kernel) |
| **LlamaIndex** | ✅ Full | Python Callable | [See below](#llamaindex) |
| **Haystack** | ✅ Full | Python Callable | [See below](#haystack) |
| **Custom Python** | ✅ Full | Python Callable | [See below](#custom-python) |
| **Node.js Agents** | ✅ Full | Entrypoint Mode | [See below](#nodejs) |
| **Go Agents** | ✅ Full | Entrypoint Mode | [See below](#go) |
| **Rust Agents** | ✅ Full | Entrypoint Mode | [See below](#rust) |
| **Any CLI Tool** | ✅ Full | Entrypoint Mode | [See below](#cli-tools) |

## Integration Methods

### Method 1: Python Callable Injection (Recommended for Python Frameworks)

**How it works:**
1. Define your agent logic as a Python function
2. SDK serializes the function with `cloudpickle`
3. Function executes inside isolated container
4. Results are collected and returned

**Advantages:**
- ✅ Simple integration - just wrap your agent in a function
- ✅ Automatic dependency management via `pip_packages`
- ✅ Full Python ecosystem support
- ✅ Easy debugging and testing

**Example:**
```python
from isolated_agents_sdk import run_agent, Policy

def my_agent():
    # Your agent logic here - works with ANY Python framework
    from your_framework import Agent
    agent = Agent()
    result = agent.run()
    return result

result = run_agent(
    agent=my_agent,
    working_dir="./workspace",
    policy=Policy(
        pip_packages=["your-framework"],
        network=NetworkPolicy(disabled=False),
    ),
)
```

### Method 2: Entrypoint Mode (Universal - Any Language)

**How it works:**
1. Provide a command to execute (e.g., `["node", "agent.js"]`)
2. SDK creates container with specified base image
3. Command executes inside isolated container
4. Output artifacts are collected

**Advantages:**
- ✅ Language-agnostic - Python, Node.js, Go, Rust, etc.
- ✅ Works with compiled binaries
- ✅ Supports any CLI tool or script
- ✅ Full control over execution environment

**Example:**
```python
from isolated_agents_sdk import run_agent, Policy

result = run_agent(
    agent=None,  # No Python callable needed
    working_dir="./workspace",
    policy=Policy(
        entrypoint=["node", "agent.js"],  # Any command
        base_image="node:20-slim",  # Any container image
        network=NetworkPolicy(disabled=False),
    ),
)
```

## Framework-Specific Examples

### LangChain

**Use Case:** Isolate LangChain agents with API access

```python
from isolated_agents_sdk import run_agent, Policy, NetworkPolicy

def langchain_agent():
    """LangChain agent running in isolation."""
    from langchain_groq import ChatGroq
    from langchain.agents import AgentExecutor, create_react_agent
    from langchain.tools import Tool
    from pathlib import Path
    
    # Initialize LLM
    llm = ChatGroq(model="llama-3.3-70b-versatile")
    
    # Define tools
    def read_file(filename: str) -> str:
        return Path(f"/workspace/{filename}").read_text()
    
    tools = [
        Tool(name="ReadFile", func=read_file, description="Read a file"),
    ]
    
    # Create agent
    agent = create_react_agent(llm, tools, prompt_template)
    executor = AgentExecutor(agent=agent, tools=tools)
    
    # Run agent
    result = executor.invoke({"input": "Analyze the data"})
    
    # Write output
    Path("/output/result.json").write_text(json.dumps(result))

result = run_agent(
    agent=langchain_agent,
    working_dir="./data",
    policy=Policy(
        pip_packages=["langchain", "langchain-groq"],
        allowed_env_vars=["GROQ_API_KEY"],
        network=NetworkPolicy(disabled=False),
        memory_mb=1024,
    ),
)
```

### AutoGPT

**Use Case:** Run AutoGPT in isolated environment

```python
from isolated_agents_sdk import run_agent, Policy, NetworkPolicy

result = run_agent(
    agent=None,
    working_dir="./autogpt_workspace",
    policy=Policy(
        entrypoint=["python", "-m", "autogpt", "--continuous"],
        base_image="python:3.11-slim",
        pip_packages=["autogpt"],
        allowed_env_vars=["OPENAI_API_KEY"],
        network=NetworkPolicy(
            disabled=False,
            allowed_endpoints=["api.openai.com:443"],
        ),
        memory_mb=2048,
        timeout_seconds=3600,
    ),
)
```

### CrewAI

**Use Case:** Isolate multi-agent CrewAI workflows

```python
from isolated_agents_sdk import run_agent, Policy, NetworkPolicy

def crewai_workflow():
    """CrewAI multi-agent workflow in isolation."""
    from crewai import Agent, Task, Crew
    from langchain_openai import ChatOpenAI
    
    llm = ChatOpenAI(model="gpt-4")
    
    # Define agents
    researcher = Agent(
        role="Researcher",
        goal="Research the topic",
        llm=llm,
    )
    
    writer = Agent(
        role="Writer",
        goal="Write a report",
        llm=llm,
    )
    
    # Define tasks
    research_task = Task(
        description="Research AI trends",
        agent=researcher,
    )
    
    write_task = Task(
        description="Write a report on findings",
        agent=writer,
    )
    
    # Create crew
    crew = Crew(
        agents=[researcher, writer],
        tasks=[research_task, write_task],
    )
    
    # Execute
    result = crew.kickoff()
    
    # Save output
    Path("/output/report.md").write_text(result)

result = run_agent(
    agent=crewai_workflow,
    working_dir="./workspace",
    policy=Policy(
        pip_packages=["crewai", "langchain-openai"],
        allowed_env_vars=["OPENAI_API_KEY"],
        network=NetworkPolicy(disabled=False),
        memory_mb=2048,
    ),
)
```

### Semantic Kernel

**Use Case:** Run Microsoft Semantic Kernel agents

```python
from isolated_agents_sdk import run_agent, Policy, NetworkPolicy

def semantic_kernel_agent():
    """Semantic Kernel agent in isolation."""
    import semantic_kernel as sk
    from semantic_kernel.connectors.ai.open_ai import OpenAIChatCompletion
    
    kernel = sk.Kernel()
    kernel.add_chat_service(
        "chat",
        OpenAIChatCompletion("gpt-4", api_key=os.environ["OPENAI_API_KEY"]),
    )
    
    # Define skills
    @kernel.skill(name="FileReader")
    def read_file(filename: str) -> str:
        return Path(f"/workspace/{filename}").read_text()
    
    # Execute
    result = kernel.run("Analyze the data in data.csv")
    
    # Save output
    Path("/output/analysis.txt").write_text(str(result))

result = run_agent(
    agent=semantic_kernel_agent,
    working_dir="./data",
    policy=Policy(
        pip_packages=["semantic-kernel"],
        allowed_env_vars=["OPENAI_API_KEY"],
        network=NetworkPolicy(disabled=False),
    ),
)
```

### LlamaIndex

**Use Case:** Isolate LlamaIndex RAG applications

```python
from isolated_agents_sdk import run_agent, Policy, NetworkPolicy

def llamaindex_rag():
    """LlamaIndex RAG in isolation."""
    from llama_index import VectorStoreIndex, SimpleDirectoryReader
    from llama_index.llms import OpenAI
    
    # Load documents
    documents = SimpleDirectoryReader("/workspace/docs").load_data()
    
    # Create index
    index = VectorStoreIndex.from_documents(documents)
    
    # Query
    query_engine = index.as_query_engine()
    response = query_engine.query("What are the key findings?")
    
    # Save output
    Path("/output/summary.txt").write_text(str(response))

result = run_agent(
    agent=llamaindex_rag,
    working_dir="./documents",
    policy=Policy(
        pip_packages=["llama-index", "llama-index-llms-openai"],
        allowed_env_vars=["OPENAI_API_KEY"],
        network=NetworkPolicy(disabled=False),
        memory_mb=2048,
    ),
)
```

### Haystack

**Use Case:** Isolate Haystack pipelines

```python
from isolated_agents_sdk import run_agent, Policy, NetworkPolicy

def haystack_pipeline():
    """Haystack pipeline in isolation."""
    from haystack import Pipeline
    from haystack.components.retrievers import InMemoryBM25Retriever
    from haystack.components.generators import OpenAIGenerator
    
    # Build pipeline
    pipeline = Pipeline()
    pipeline.add_component("retriever", InMemoryBM25Retriever())
    pipeline.add_component("generator", OpenAIGenerator())
    
    # Run pipeline
    result = pipeline.run({"query": "What is AI?"})
    
    # Save output
    Path("/output/answer.txt").write_text(result["answer"])

result = run_agent(
    agent=haystack_pipeline,
    working_dir="./data",
    policy=Policy(
        pip_packages=["haystack-ai"],
        allowed_env_vars=["OPENAI_API_KEY"],
        network=NetworkPolicy(disabled=False),
    ),
)
```

### Custom Python

**Use Case:** Any custom Python agent framework

```python
from isolated_agents_sdk import run_agent, Policy

def custom_agent():
    """Your custom agent implementation."""
    # Import your custom framework
    from my_custom_framework import MyAgent
    
    # Initialize agent
    agent = MyAgent(config="/workspace/config.yaml")
    
    # Run agent logic
    result = agent.execute()
    
    # Write output
    Path("/output/result.json").write_text(json.dumps(result))

result = run_agent(
    agent=custom_agent,
    working_dir="./workspace",
    policy=Policy(
        pip_packages=["my-custom-framework"],
        # ... other settings
    ),
)
```

### Node.js

**Use Case:** Isolate Node.js agents (e.g., LangChain.js)

```python
from isolated_agents_sdk import run_agent, Policy, NetworkPolicy

result = run_agent(
    agent=None,
    working_dir="./nodejs_agent",
    policy=Policy(
        entrypoint=["node", "agent.js"],
        base_image="node:20-slim",
        allowed_env_vars=["OPENAI_API_KEY"],
        network=NetworkPolicy(disabled=False),
        memory_mb=1024,
    ),
)
```

**agent.js:**
```javascript
// Any Node.js agent framework
const { ChatOpenAI } = require("@langchain/openai");
const fs = require("fs");

async function main() {
    const llm = new ChatOpenAI({ modelName: "gpt-4" });
    const result = await llm.invoke("Analyze the data");
    
    fs.writeFileSync("/output/result.txt", result.content);
}

main();
```

### Go

**Use Case:** Isolate Go-based agents

```python
from isolated_agents_sdk import run_agent, Policy

result = run_agent(
    agent=None,
    working_dir="./go_agent",
    policy=Policy(
        entrypoint=["./agent"],  # Pre-compiled binary
        base_image="golang:1.21-alpine",
        network=NetworkPolicy(disabled=False),
    ),
)
```

### Rust

**Use Case:** Isolate Rust-based agents

```python
from isolated_agents_sdk import run_agent, Policy

result = run_agent(
    agent=None,
    working_dir="./rust_agent",
    policy=Policy(
        entrypoint=["./target/release/agent"],
        base_image="rust:1.75-slim",
        network=NetworkPolicy(disabled=False),
    ),
)
```

### CLI Tools

**Use Case:** Isolate any CLI tool as an "agent"

```python
from isolated_agents_sdk import run_agent, Policy

# Example: Run ffmpeg as an isolated "agent"
result = run_agent(
    agent=None,
    working_dir="./videos",
    policy=Policy(
        entrypoint=["ffmpeg", "-i", "input.mp4", "/output/output.mp4"],
        base_image="jrottenberg/ffmpeg:latest",
        network=NetworkPolicy(disabled=True),
    ),
)
```

## Universal Patterns

### Pattern 1: Framework Wrapper

Create a reusable wrapper for your framework:

```python
from isolated_agents_sdk import run_agent, Policy, NetworkPolicy

class IsolatedFrameworkRunner:
    """Universal wrapper for any agent framework."""
    
    def __init__(self, framework_name: str, pip_packages: list[str]):
        self.framework_name = framework_name
        self.pip_packages = pip_packages
    
    def run(self, agent_func, working_dir: str, **policy_kwargs):
        """Run any agent function in isolation."""
        policy = Policy(
            pip_packages=self.pip_packages,
            network=NetworkPolicy(disabled=False),
            **policy_kwargs,
        )
        
        return run_agent(
            agent=agent_func,
            working_dir=working_dir,
            policy=policy,
        )

# Usage with any framework
langchain_runner = IsolatedFrameworkRunner(
    framework_name="langchain",
    pip_packages=["langchain", "langchain-openai"],
)

result = langchain_runner.run(my_langchain_agent, "./workspace")
```

### Pattern 2: Multi-Framework Pipeline

Run multiple frameworks in sequence:

```python
from isolated_agents_sdk import run_agent, Policy

# Step 1: LangChain for research
research_result = run_agent(
    agent=langchain_research_agent,
    working_dir="./workspace",
    policy=Policy(pip_packages=["langchain"]),
)

# Step 2: CrewAI for analysis
analysis_result = run_agent(
    agent=crewai_analysis_agent,
    working_dir="./workspace",  # Same workspace
    policy=Policy(pip_packages=["crewai"]),
)

# Step 3: Custom framework for reporting
report_result = run_agent(
    agent=custom_report_agent,
    working_dir="./workspace",
    policy=Policy(pip_packages=["my-framework"]),
)
```

### Pattern 3: Polyglot Agents

Mix languages in a single workflow:

```python
# Python agent generates data
python_result = run_agent(
    agent=python_data_generator,
    working_dir="./workspace",
    policy=Policy(pip_packages=["pandas"]),
)

# Node.js agent processes data
nodejs_result = run_agent(
    agent=None,
    working_dir="./workspace",
    policy=Policy(
        entrypoint=["node", "process.js"],
        base_image="node:20-slim",
    ),
)

# Go agent serves results
go_result = run_agent(
    agent=None,
    working_dir="./workspace",
    policy=Policy(
        entrypoint=["./server"],
        base_image="golang:1.21-alpine",
    ),
)
```

## Key Benefits as Universal Sandbox

### 1. Framework Independence
- ✅ Works with ANY Python framework (LangChain, CrewAI, custom, etc.)
- ✅ Works with ANY language (Node.js, Go, Rust, etc.)
- ✅ Works with ANY CLI tool
- ✅ No framework-specific code in SDK

### 2. Security Isolation
- ✅ Each agent runs in isolated container
- ✅ Network access controlled per agent
- ✅ Filesystem access restricted
- ✅ Resource limits enforced

### 3. Reproducibility
- ✅ Same container image = same environment
- ✅ Dependency versions locked
- ✅ No "works on my machine" issues

### 4. Flexibility
- ✅ Mix frameworks in same project
- ✅ Upgrade frameworks without breaking others
- ✅ Test different frameworks easily

### 5. Production Ready
- ✅ Audit logging for all frameworks
- ✅ Resource monitoring
- ✅ Timeout enforcement
- ✅ Error handling

## Migration Guide for Existing Agents

### From Bare Python to Isolated

**Before:**
```python
from my_framework import Agent

agent = Agent()
result = agent.run()
```

**After:**
```python
from isolated_agents_sdk import run_agent, Policy

def isolated_agent():
    from my_framework import Agent
    agent = Agent()
    result = agent.run()
    Path("/output/result.json").write_text(json.dumps(result))

result = run_agent(
    agent=isolated_agent,
    working_dir="./workspace",
    policy=Policy(pip_packages=["my-framework"]),
)
```

### From Docker Compose to SDK

**Before (docker-compose.yml):**
```yaml
services:
  agent:
    image: python:3.11
    volumes:
      - ./workspace:/workspace
    command: python agent.py
```

**After:**
```python
from isolated_agents_sdk import run_agent, Policy

result = run_agent(
    agent=None,
    working_dir="./workspace",
    policy=Policy(
        entrypoint=["python", "agent.py"],
        base_image="python:3.11",
    ),
)
```

## Conclusion

The Isolated Agents SDK is a **universal local sandbox** that works with:
- ✅ **Any Python framework** (LangChain, CrewAI, AutoGPT, custom, etc.)
- ✅ **Any programming language** (Node.js, Go, Rust, etc.)
- ✅ **Any CLI tool** (ffmpeg, curl, custom scripts, etc.)
- ✅ **Any container image** (Python, Node, Go, custom, etc.)

It provides **secure isolation**, **resource control**, and **audit logging** for ANY agent, regardless of implementation. The adapter pattern makes it production-ready for enterprise deployments while remaining simple for local development.

---

**Key Takeaway**: This SDK is not tied to any specific framework. It's a universal sandbox that isolates and secures ANY agent execution, making it the perfect foundation for building safe, scalable agent systems.