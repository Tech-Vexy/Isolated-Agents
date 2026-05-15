# Decorators - Simplified Agent Definition

## Overview

The Isolated Agents SDK provides a powerful decorator system that makes defining and running isolated agents incredibly simple. Decorators provide a clean, Pythonic way to configure agents with policies, telemetry, and resource limits using simple annotations.

## Quick Example

```python
from isolated_agents_sdk import isolated_agent, Policy, NetworkPolicy

@isolated_agent(
    working_dir="./workspace",
    policy=Policy(
        memory_mb=1024,
        network=NetworkPolicy(disabled=False),
        pip_packages=["langchain", "langchain-openai"],
    ),
)
def my_research_agent(query: str) -> dict:
    """Research agent that runs in isolation."""
    from langchain_openai import ChatOpenAI
    from pathlib import Path
    
    llm = ChatOpenAI(model="gpt-4")
    result = llm.invoke(query)
    
    # Write output
    Path("/output/result.txt").write_text(result.content)
    
    return {"status": "success", "result": result.content}

# Use it like a normal function - isolation is automatic!
result = my_research_agent("What are the latest AI trends?")
print(result.exit_code)  # 0
print(result.artifacts)  # {"result.txt": "/tmp/..."}
```

## Core Decorators

### 1. `@isolated_agent` - Main Decorator

The primary decorator for creating isolated agents.

```python
from isolated_agents_sdk import isolated_agent, Policy

@isolated_agent(
    working_dir="./workspace",
    policy=Policy(memory_mb=512),
    host_output_path="./output",
)
def my_agent():
    # Agent code here
    pass

# Call like a normal function
result = my_agent()
```

**Parameters:**
- `working_dir` (str | Path): Host directory mounted as `/workspace`
- `policy` (Policy | None): Security and resource policy
- `host_output_path` (str | Path | None): Where to save artifacts
- `async_mode` (bool): If True, returns coroutine (default: False)

**Returns:**
- `AgentResult` with exit_code, artifacts, and session_id

### 2. `@policy` - Policy Configuration

Configure policy settings directly on the function.

```python
from isolated_agents_sdk import isolated_agent, policy

@isolated_agent(working_dir="./workspace")
@policy(
    memory_mb=1024,
    cpu_cores=2.0,
    timeout_seconds=300,
)
def my_agent():
    pass
```

### 3. `@network` - Network Configuration

Configure network access with a dedicated decorator.

```python
from isolated_agents_sdk import isolated_agent, network

@isolated_agent(working_dir="./workspace")
@network(
    enabled=True,
    allowed_endpoints=["api.openai.com:443", "api.anthropic.com:443"],
)
def my_agent():
    pass
```

### 4. `@resources` - Resource Limits

Set CPU and memory limits.

```python
from isolated_agents_sdk import isolated_agent, resources

@isolated_agent(working_dir="./workspace")
@resources(cpu_cores=2.0, memory_mb=2048)
def my_agent():
    pass
```

### 5. `@dependencies` - Package Dependencies

Specify pip packages to install.

```python
from isolated_agents_sdk import isolated_agent, dependencies

@isolated_agent(working_dir="./workspace")
@dependencies("langchain", "langchain-openai", "pandas")
def my_agent():
    pass
```

### 6. `@timeout` - Execution Timeout

Set maximum execution time.

```python
from isolated_agents_sdk import isolated_agent, timeout

@isolated_agent(working_dir="./workspace")
@timeout(seconds=300)  # 5 minutes
def my_agent():
    pass
```

### 7. `@telemetry` - Telemetry Configuration

Configure real-time telemetry logging.

```python
from isolated_agents_sdk import isolated_agent, telemetry

@isolated_agent(working_dir="./workspace")
@telemetry(enabled=True, level="INFO", format="rich")
def my_agent():
    pass
```

### 8. `@retry` - Automatic Retry

Automatically retry on failure.

```python
from isolated_agents_sdk import isolated_agent, retry

@isolated_agent(working_dir="./workspace")
@retry(max_attempts=3, backoff=2.0)
def my_agent():
    pass
```

### 9. `@cache` - Result Caching

Cache agent results based on inputs.

```python
from isolated_agents_sdk import isolated_agent, cache

@isolated_agent(working_dir="./workspace")
@cache(ttl=3600)  # Cache for 1 hour
def my_agent(query: str):
    pass
```

### 10. `@async_isolated_agent` - Async Variant

For async agent functions.

```python
from isolated_agents_sdk import async_isolated_agent

@async_isolated_agent(working_dir="./workspace")
async def my_async_agent():
    pass

# Use with await
result = await my_async_agent()
```

## Decorator Combinations

### Example 1: Full-Featured Agent

```python
from isolated_agents_sdk import (
    isolated_agent,
    policy,
    network,
    dependencies,
    timeout,
    telemetry,
    retry,
)

@isolated_agent(working_dir="./workspace", host_output_path="./output")
@policy(memory_mb=2048, cpu_cores=2.0)
@network(enabled=True, allowed_endpoints=["api.openai.com:443"])
@dependencies("langchain", "langchain-openai", "pandas")
@timeout(seconds=600)
@telemetry(enabled=True, level="INFO")
@retry(max_attempts=3)
def research_agent(topic: str) -> dict:
    """Comprehensive research agent with full configuration."""
    from langchain_openai import ChatOpenAI
    from pathlib import Path
    import pandas as pd
    
    # Research logic
    llm = ChatOpenAI(model="gpt-4")
    result = llm.invoke(f"Research: {topic}")
    
    # Save results
    Path("/output/research.txt").write_text(result.content)
    
    return {"status": "success", "topic": topic}

# Use it
result = research_agent("AI Safety")
```

### Example 2: Simple Agent

```python
from isolated_agents_sdk import isolated_agent

@isolated_agent(working_dir="./data")
def process_data():
    """Simple data processing agent."""
    from pathlib import Path
    import json
    
    data = json.loads(Path("/workspace/input.json").read_text())
    processed = {"count": len(data), "items": data}
    Path("/output/result.json").write_text(json.dumps(processed))

result = process_data()
```

### Example 3: Async Agent with Caching

```python
from isolated_agents_sdk import async_isolated_agent, cache, dependencies

@async_isolated_agent(working_dir="./workspace")
@cache(ttl=3600)
@dependencies("aiohttp", "asyncio")
async def fetch_data(url: str):
    """Async agent with result caching."""
    import aiohttp
    from pathlib import Path
    
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            data = await response.text()
            Path("/output/data.txt").write_text(data)
    
    return {"url": url, "size": len(data)}

# Use with await
result = await fetch_data("https://api.example.com/data")
```

## Advanced Decorator Features

### Parameterized Decorators

Pass parameters to agents through decorator configuration:

```python
from isolated_agents_sdk import isolated_agent

@isolated_agent(working_dir="./workspace")
def parameterized_agent(input_file: str, output_file: str):
    """Agent that accepts parameters."""
    from pathlib import Path
    
    data = Path(f"/workspace/{input_file}").read_text()
    processed = data.upper()
    Path(f"/output/{output_file}").write_text(processed)

# Call with parameters
result = parameterized_agent("input.txt", "output.txt")
```

### Dynamic Policy Configuration

Configure policy based on function arguments:

```python
from isolated_agents_sdk import isolated_agent, Policy

def get_policy(memory_mb: int) -> Policy:
    """Dynamic policy based on requirements."""
    return Policy(
        memory_mb=memory_mb,
        cpu_cores=memory_mb / 512,  # Scale CPU with memory
    )

@isolated_agent(
    working_dir="./workspace",
    policy=lambda: get_policy(2048),
)
def dynamic_agent():
    pass
```

### Conditional Isolation

Only isolate in certain conditions:

```python
from isolated_agents_sdk import isolated_agent
import os

@isolated_agent(
    working_dir="./workspace",
    enabled=os.getenv("ISOLATE", "true").lower() == "true",
)
def conditional_agent():
    """Only isolated if ISOLATE=true."""
    pass
```

### Decorator Inheritance

Create custom decorators by composing existing ones:

```python
from isolated_agents_sdk import isolated_agent, policy, network, dependencies
from functools import wraps

def langchain_agent(working_dir: str):
    """Custom decorator for LangChain agents."""
    def decorator(func):
        @isolated_agent(working_dir=working_dir)
        @policy(memory_mb=1024)
        @network(enabled=True)
        @dependencies("langchain", "langchain-openai")
        @wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)
        return wrapper
    return decorator

# Use custom decorator
@langchain_agent(working_dir="./workspace")
def my_langchain_agent():
    from langchain_openai import ChatOpenAI
    # Agent logic
    pass
```

## Decorator Implementation

### Base Decorator Class

```python
from functools import wraps
from typing import Callable, Optional
from isolated_agents_sdk import run_agent, async_run_agent, Policy

class IsolatedAgentDecorator:
    """Base decorator for isolated agents."""
    
    def __init__(
        self,
        working_dir: str,
        policy: Optional[Policy] = None,
        host_output_path: Optional[str] = None,
        async_mode: bool = False,
    ):
        self.working_dir = working_dir
        self.policy = policy or Policy()
        self.host_output_path = host_output_path
        self.async_mode = async_mode
    
    def __call__(self, func: Callable) -> Callable:
        """Wrap the function to run in isolation."""
        if self.async_mode:
            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                # Create agent function that calls original with args
                def agent():
                    return func(*args, **kwargs)
                
                return await async_run_agent(
                    agent=agent,
                    working_dir=self.working_dir,
                    policy=self.policy,
                    host_output_path=self.host_output_path,
                )
            return async_wrapper
        else:
            @wraps(func)
            def sync_wrapper(*args, **kwargs):
                # Create agent function that calls original with args
                def agent():
                    return func(*args, **kwargs)
                
                return run_agent(
                    agent=agent,
                    working_dir=self.working_dir,
                    policy=self.policy,
                    host_output_path=self.host_output_path,
                )
            return sync_wrapper

# Public API
def isolated_agent(
    working_dir: str,
    policy: Optional[Policy] = None,
    host_output_path: Optional[str] = None,
):
    """Decorator to run a function in an isolated container."""
    return IsolatedAgentDecorator(working_dir, policy, host_output_path, async_mode=False)

def async_isolated_agent(
    working_dir: str,
    policy: Optional[Policy] = None,
    host_output_path: Optional[str] = None,
):
    """Async decorator to run a function in an isolated container."""
    return IsolatedAgentDecorator(working_dir, policy, host_output_path, async_mode=True)
```

### Policy Modifier Decorators

```python
def policy(**kwargs):
    """Decorator to modify policy settings."""
    def decorator(func):
        if hasattr(func, '_isolated_policy'):
            # Update existing policy
            for key, value in kwargs.items():
                setattr(func._isolated_policy, key, value)
        else:
            # Create new policy
            func._isolated_policy = Policy(**kwargs)
        return func
    return decorator

def network(enabled: bool = True, allowed_endpoints: list[str] = None):
    """Decorator to configure network access."""
    def decorator(func):
        if not hasattr(func, '_isolated_policy'):
            func._isolated_policy = Policy()
        
        func._isolated_policy.network = NetworkPolicy(
            disabled=not enabled,
            allowed_endpoints=allowed_endpoints or [],
        )
        return func
    return decorator

def resources(cpu_cores: float, memory_mb: int):
    """Decorator to set resource limits."""
    def decorator(func):
        if not hasattr(func, '_isolated_policy'):
            func._isolated_policy = Policy()
        
        func._isolated_policy.cpu_cores = cpu_cores
        func._isolated_policy.memory_mb = memory_mb
        return func
    return decorator

def dependencies(*packages: str):
    """Decorator to specify pip dependencies."""
    def decorator(func):
        if not hasattr(func, '_isolated_policy'):
            func._isolated_policy = Policy()
        
        func._isolated_policy.pip_packages = list(packages)
        return func
    return decorator

def timeout(seconds: int):
    """Decorator to set execution timeout."""
    def decorator(func):
        if not hasattr(func, '_isolated_policy'):
            func._isolated_policy = Policy()
        
        func._isolated_policy.timeout_seconds = seconds
        return func
    return decorator

def telemetry(enabled: bool = True, level: str = "INFO", format: str = "rich"):
    """Decorator to configure telemetry."""
    def decorator(func):
        if not hasattr(func, '_isolated_policy'):
            func._isolated_policy = Policy()
        
        func._isolated_policy.telemetry_enabled = enabled
        func._isolated_policy.telemetry_level = level
        func._isolated_policy.telemetry_format = format
        return func
    return decorator
```

### Retry Decorator

```python
import time
from functools import wraps

def retry(max_attempts: int = 3, backoff: float = 1.0):
    """Decorator to retry agent execution on failure."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(max_attempts):
                try:
                    result = func(*args, **kwargs)
                    if result.exit_code == 0:
                        return result
                    last_exception = RuntimeError(f"Agent failed with exit code {result.exit_code}")
                except Exception as e:
                    last_exception = e
                
                if attempt < max_attempts - 1:
                    time.sleep(backoff * (2 ** attempt))  # Exponential backoff
            
            raise last_exception
        return wrapper
    return decorator
```

### Cache Decorator

```python
import hashlib
import json
import pickle
from functools import wraps
from pathlib import Path

def cache(ttl: int = 3600, cache_dir: str = "./.agent_cache"):
    """Decorator to cache agent results."""
    def decorator(func):
        cache_path = Path(cache_dir)
        cache_path.mkdir(exist_ok=True)
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Generate cache key from function name and arguments
            key_data = {
                "func": func.__name__,
                "args": args,
                "kwargs": kwargs,
            }
            key = hashlib.sha256(json.dumps(key_data, sort_keys=True).encode()).hexdigest()
            cache_file = cache_path / f"{key}.pkl"
            
            # Check cache
            if cache_file.exists():
                import time
                if time.time() - cache_file.stat().st_mtime < ttl:
                    with open(cache_file, "rb") as f:
                        return pickle.load(f)
            
            # Execute and cache
            result = func(*args, **kwargs)
            with open(cache_file, "wb") as f:
                pickle.dump(result, f)
            
            return result
        return wrapper
    return decorator
```

## Real-World Examples

### Example 1: Data Processing Pipeline

```python
from isolated_agents_sdk import isolated_agent, resources, timeout

@isolated_agent(working_dir="./data")
@resources(cpu_cores=4.0, memory_mb=4096)
@timeout(seconds=1800)
def process_large_dataset():
    """Process large dataset with high resources."""
    import pandas as pd
    from pathlib import Path
    
    # Load data
    df = pd.read_csv("/workspace/large_data.csv")
    
    # Process
    result = df.groupby("category").agg({"value": "sum"})
    
    # Save
    result.to_csv("/output/processed.csv")

result = process_large_dataset()
```

### Example 2: Multi-Agent System

```python
from isolated_agents_sdk import isolated_agent, network, dependencies

@isolated_agent(working_dir="./workspace")
@network(enabled=True, allowed_endpoints=["api.openai.com:443"])
@dependencies("langchain", "langchain-openai")
def researcher(topic: str):
    """Research agent."""
    from langchain_openai import ChatOpenAI
    from pathlib import Path
    
    llm = ChatOpenAI(model="gpt-4")
    research = llm.invoke(f"Research: {topic}")
    Path("/output/research.txt").write_text(research.content)
    return research.content

@isolated_agent(working_dir="./workspace")
@dependencies("langchain", "langchain-openai")
def writer(research: str):
    """Writer agent."""
    from langchain_openai import ChatOpenAI
    from pathlib import Path
    
    llm = ChatOpenAI(model="gpt-4")
    article = llm.invoke(f"Write article based on: {research}")
    Path("/output/article.txt").write_text(article.content)
    return article.content

# Run multi-agent pipeline
research_result = researcher("AI Safety")
article_result = writer(research_result.artifacts["research.txt"])
```

### Example 3: Scheduled Agent

```python
from isolated_agents_sdk import isolated_agent, retry, telemetry
import schedule
import time

@isolated_agent(working_dir="./workspace")
@retry(max_attempts=3)
@telemetry(enabled=True, level="INFO")
def daily_report():
    """Generate daily report."""
    from pathlib import Path
    from datetime import datetime
    
    report = f"Daily Report - {datetime.now()}\n"
    # Generate report logic
    Path("/output/daily_report.txt").write_text(report)

# Schedule to run daily
schedule.every().day.at("09:00").do(daily_report)

while True:
    schedule.run_pending()
    time.sleep(60)
```

## Benefits of Decorators

### 1. Clean Syntax
- ✅ Pythonic and intuitive
- ✅ Self-documenting code
- ✅ Easy to read and maintain

### 2. Composability
- ✅ Stack multiple decorators
- ✅ Create custom decorators
- ✅ Reuse configurations

### 3. Flexibility
- ✅ Mix with regular functions
- ✅ Conditional isolation
- ✅ Dynamic configuration

### 4. Productivity
- ✅ Less boilerplate code
- ✅ Faster development
- ✅ Easier testing

## Best Practices

1. **Use decorators for simple cases** - For complex scenarios, use the functional API
2. **Stack decorators logically** - Put `@isolated_agent` first, then modifiers
3. **Keep agents focused** - One agent, one responsibility
4. **Document decorator usage** - Add docstrings explaining configuration
5. **Test with and without isolation** - Use `enabled=False` for local testing

---

**Decorators make the Isolated Agents SDK incredibly easy to use, providing a clean, Pythonic way to define and configure isolated agents with minimal boilerplate code.**