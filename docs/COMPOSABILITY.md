# Agent Composability Guide

## Overview

The Isolated Agents SDK provides powerful **composability patterns** that enable you to:
- Chain multiple agents together in pipelines
- Create parallel agent execution workflows
- Build hierarchical agent systems
- Share data between isolated agents
- Compose complex multi-agent architectures

## Table of Contents

1. [Sequential Composition](#sequential-composition)
2. [Parallel Composition](#parallel-composition)
3. [Hierarchical Composition](#hierarchical-composition)
4. [Pipeline Composition](#pipeline-composition)
5. [Conditional Composition](#conditional-composition)
6. [Data Flow Patterns](#data-flow-patterns)
7. [Error Handling in Compositions](#error-handling-in-compositions)
8. [Advanced Patterns](#advanced-patterns)

---

## Sequential Composition

### Basic Sequential Chain

Execute agents one after another, passing outputs as inputs:

```python
from isolated_agents_sdk import isolated_agent, network, dependencies

@isolated_agent(working_dir="./workspace")
@network(enabled=True)
@dependencies("langchain", "langchain-openai")
def researcher(topic: str):
    """Research agent that gathers information."""
    from langchain_openai import ChatOpenAI
    from pathlib import Path
    
    llm = ChatOpenAI(model="gpt-4")
    research = llm.invoke(f"Research the topic: {topic}")
    
    # Save research to output
    Path("/output/research.txt").write_text(research.content)
    return {"status": "success", "topic": topic}

@isolated_agent(working_dir="./workspace")
@dependencies("langchain", "langchain-openai")
def writer(research_file: str):
    """Writer agent that creates content from research."""
    from langchain_openai import ChatOpenAI
    from pathlib import Path
    
    # Read research from previous agent
    research = Path(research_file).read_text()
    
    llm = ChatOpenAI(model="gpt-4")
    article = llm.invoke(f"Write an article based on: {research}")
    
    Path("/output/article.txt").write_text(article.content)
    return {"status": "success", "article_length": len(article.content)}

@isolated_agent(working_dir="./workspace")
@dependencies("langchain", "langchain-openai")
def editor(article_file: str):
    """Editor agent that polishes content."""
    from langchain_openai import ChatOpenAI
    from pathlib import Path
    
    article = Path(article_file).read_text()
    
    llm = ChatOpenAI(model="gpt-4")
    edited = llm.invoke(f"Edit and improve: {article}")
    
    Path("/output/final.txt").write_text(edited.content)
    return {"status": "success", "final_length": len(edited.content)}

# Execute sequential chain
result1 = researcher("AI Safety")
result2 = writer(result1.artifacts["research.txt"])
result3 = editor(result2.artifacts["article.txt"])

print(f"Final article: {result3.artifacts['final.txt']}")
```

### Using the `@chain` Decorator

Simplify sequential composition with the `@chain` decorator:

```python
from isolated_agents_sdk import chain, isolated_agent

@chain(
    agents=[researcher, writer, editor],
    data_flow="sequential"  # Pass outputs to next agent
)
def content_pipeline(topic: str):
    """Automatically chains researcher -> writer -> editor."""
    pass

# Execute entire chain with one call
result = content_pipeline("AI Safety")
print(f"Final output: {result.artifacts['final.txt']}")
```

---

## Parallel Composition

### Basic Parallel Execution

Run multiple agents concurrently:

```python
from isolated_agents_sdk import isolated_agent, parallel
import asyncio

@isolated_agent(working_dir="./workspace")
@network(enabled=True)
@dependencies("langchain", "langchain-openai")
async def research_technical(topic: str):
    """Research technical aspects."""
    from langchain_openai import ChatOpenAI
    from pathlib import Path
    
    llm = ChatOpenAI(model="gpt-4")
    result = llm.invoke(f"Research technical aspects of: {topic}")
    Path("/output/technical.txt").write_text(result.content)
    return {"aspect": "technical"}

@isolated_agent(working_dir="./workspace")
@network(enabled=True)
@dependencies("langchain", "langchain-openai")
async def research_business(topic: str):
    """Research business aspects."""
    from langchain_openai import ChatOpenAI
    from pathlib import Path
    
    llm = ChatOpenAI(model="gpt-4")
    result = llm.invoke(f"Research business aspects of: {topic}")
    Path("/output/business.txt").write_text(result.content)
    return {"aspect": "business"}

@isolated_agent(working_dir="./workspace")
@network(enabled=True)
@dependencies("langchain", "langchain-openai")
async def research_social(topic: str):
    """Research social aspects."""
    from langchain_openai import ChatOpenAI
    from pathlib import Path
    
    llm = ChatOpenAI(model="gpt-4")
    result = llm.invoke(f"Research social aspects of: {topic}")
    Path("/output/social.txt").write_text(result.content)
    return {"aspect": "social"}

# Execute in parallel
results = await asyncio.gather(
    research_technical("AI Safety"),
    research_business("AI Safety"),
    research_social("AI Safety")
)

print(f"Completed {len(results)} research tasks in parallel")
```

### Using the `@parallel` Decorator

Simplify parallel execution:

```python
from isolated_agents_sdk import parallel

@parallel(
    agents=[research_technical, research_business, research_social],
    max_concurrent=3  # Run up to 3 agents concurrently
)
async def comprehensive_research(topic: str):
    """Automatically runs all research agents in parallel."""
    pass

# Execute all agents concurrently
results = await comprehensive_research("AI Safety")
print(f"Technical: {results[0].artifacts['technical.txt']}")
print(f"Business: {results[1].artifacts['business.txt']}")
print(f"Social: {results[2].artifacts['social.txt']}")
```

---

## Hierarchical Composition

### Manager-Worker Pattern

Create hierarchical agent systems with managers and workers:

```python
from isolated_agents_sdk import isolated_agent, hierarchical

@isolated_agent(working_dir="./workspace")
@dependencies("langchain", "langchain-openai")
def task_planner(goal: str):
    """Manager agent that breaks down tasks."""
    from langchain_openai import ChatOpenAI
    from pathlib import Path
    import json
    
    llm = ChatOpenAI(model="gpt-4")
    plan = llm.invoke(f"Break down this goal into subtasks: {goal}")
    
    # Parse subtasks
    subtasks = [
        {"id": 1, "task": "Research topic"},
        {"id": 2, "task": "Write draft"},
        {"id": 3, "task": "Review and edit"}
    ]
    
    Path("/output/plan.json").write_text(json.dumps(subtasks))
    return {"subtasks": subtasks}

@isolated_agent(working_dir="./workspace")
@network(enabled=True)
@dependencies("langchain", "langchain-openai")
def worker(subtask: dict):
    """Worker agent that executes subtasks."""
    from langchain_openai import ChatOpenAI
    from pathlib import Path
    
    llm = ChatOpenAI(model="gpt-4")
    result = llm.invoke(f"Execute subtask: {subtask['task']}")
    
    Path(f"/output/subtask_{subtask['id']}.txt").write_text(result.content)
    return {"subtask_id": subtask["id"], "status": "completed"}

@isolated_agent(working_dir="./workspace")
@dependencies("langchain", "langchain-openai")
def aggregator(results: list):
    """Aggregator agent that combines results."""
    from pathlib import Path
    
    combined = "\n\n".join([
        Path(f"/output/subtask_{r['subtask_id']}.txt").read_text()
        for r in results
    ])
    
    Path("/output/final_result.txt").write_text(combined)
    return {"status": "aggregated", "total_subtasks": len(results)}

# Execute hierarchical workflow
plan = task_planner("Create comprehensive AI Safety report")
worker_results = [worker(subtask) for subtask in plan.return_value["subtasks"]]
final = aggregator(worker_results)

print(f"Final result: {final.artifacts['final_result.txt']}")
```

### Using the `@hierarchical` Decorator

```python
from isolated_agents_sdk import hierarchical

@hierarchical(
    manager=task_planner,
    workers=[worker],
    aggregator=aggregator,
    max_workers=5  # Maximum concurrent workers
)
def hierarchical_workflow(goal: str):
    """Automatically manages hierarchical execution."""
    pass

# Execute entire hierarchy
result = hierarchical_workflow("Create comprehensive AI Safety report")
print(f"Final result: {result.artifacts['final_result.txt']}")
```

---

## Pipeline Composition

### Data Processing Pipeline

Create ETL-style pipelines with multiple stages:

```python
from isolated_agents_sdk import isolated_agent, pipeline

@isolated_agent(working_dir="./workspace")
@network(enabled=True)
@dependencies("requests", "beautifulsoup4")
def extract(url: str):
    """Extract data from source."""
    import requests
    from bs4 import BeautifulSoup
    from pathlib import Path
    
    response = requests.get(url)
    soup = BeautifulSoup(response.content, 'html.parser')
    text = soup.get_text()
    
    Path("/output/raw_data.txt").write_text(text)
    return {"status": "extracted", "size": len(text)}

@isolated_agent(working_dir="./workspace")
@dependencies("pandas")
def transform(raw_data_file: str):
    """Transform and clean data."""
    from pathlib import Path
    import re
    
    raw_data = Path(raw_data_file).read_text()
    
    # Clean and transform
    cleaned = re.sub(r'\s+', ' ', raw_data)
    cleaned = cleaned.strip()
    
    Path("/output/cleaned_data.txt").write_text(cleaned)
    return {"status": "transformed", "size": len(cleaned)}

@isolated_agent(working_dir="./workspace")
@dependencies("langchain", "langchain-openai")
def load(cleaned_data_file: str):
    """Load and analyze data."""
    from langchain_openai import ChatOpenAI
    from pathlib import Path
    
    cleaned_data = Path(cleaned_data_file).read_text()
    
    llm = ChatOpenAI(model="gpt-4")
    analysis = llm.invoke(f"Analyze this data: {cleaned_data[:1000]}")
    
    Path("/output/analysis.txt").write_text(analysis.content)
    return {"status": "loaded", "analysis_length": len(analysis.content)}

# Execute pipeline
result1 = extract("https://example.com/data")
result2 = transform(result1.artifacts["raw_data.txt"])
result3 = load(result2.artifacts["cleaned_data.txt"])

print(f"Analysis: {result3.artifacts['analysis.txt']}")
```

### Using the `@pipeline` Decorator

```python
from isolated_agents_sdk import pipeline

@pipeline(
    stages=[extract, transform, load],
    error_handling="continue"  # Continue on errors
)
def etl_pipeline(url: str):
    """Automatically executes ETL pipeline."""
    pass

# Execute entire pipeline
result = etl_pipeline("https://example.com/data")
print(f"Analysis: {result.artifacts['analysis.txt']}")
```

---

## Conditional Composition

### Branching Logic

Execute different agents based on conditions:

```python
from isolated_agents_sdk import isolated_agent, conditional

@isolated_agent(working_dir="./workspace")
@dependencies("langchain", "langchain-openai")
def classifier(text: str):
    """Classify input to determine next agent."""
    from langchain_openai import ChatOpenAI
    from pathlib import Path
    
    llm = ChatOpenAI(model="gpt-4")
    result = llm.invoke(f"Classify this text as 'technical', 'business', or 'general': {text}")
    
    category = result.content.lower().strip()
    Path("/output/category.txt").write_text(category)
    return {"category": category}

@isolated_agent(working_dir="./workspace")
@dependencies("langchain", "langchain-openai")
def technical_handler(text: str):
    """Handle technical content."""
    from langchain_openai import ChatOpenAI
    from pathlib import Path
    
    llm = ChatOpenAI(model="gpt-4")
    result = llm.invoke(f"Provide technical analysis: {text}")
    Path("/output/technical_analysis.txt").write_text(result.content)
    return {"type": "technical"}

@isolated_agent(working_dir="./workspace")
@dependencies("langchain", "langchain-openai")
def business_handler(text: str):
    """Handle business content."""
    from langchain_openai import ChatOpenAI
    from pathlib import Path
    
    llm = ChatOpenAI(model="gpt-4")
    result = llm.invoke(f"Provide business analysis: {text}")
    Path("/output/business_analysis.txt").write_text(result.content)
    return {"type": "business"}

@isolated_agent(working_dir="./workspace")
@dependencies("langchain", "langchain-openai")
def general_handler(text: str):
    """Handle general content."""
    from langchain_openai import ChatOpenAI
    from pathlib import Path
    
    llm = ChatOpenAI(model="gpt-4")
    result = llm.invoke(f"Provide general analysis: {text}")
    Path("/output/general_analysis.txt").write_text(result.content)
    return {"type": "general"}

# Execute with branching
def process_text(text: str):
    classification = classifier(text)
    category = classification.return_value["category"]
    
    if category == "technical":
        return technical_handler(text)
    elif category == "business":
        return business_handler(text)
    else:
        return general_handler(text)

result = process_text("Explain quantum computing algorithms")
print(f"Result type: {result.return_value['type']}")
```

### Using the `@conditional` Decorator

```python
from isolated_agents_sdk import conditional

@conditional(
    classifier=classifier,
    branches={
        "technical": technical_handler,
        "business": business_handler,
        "general": general_handler
    },
    default="general"  # Default branch if no match
)
def smart_processor(text: str):
    """Automatically routes to appropriate handler."""
    pass

# Execute with automatic routing
result = smart_processor("Explain quantum computing algorithms")
print(f"Result type: {result.return_value['type']}")
```

---

## Data Flow Patterns

### Shared State Pattern

Share data between agents using shared storage:

```python
from isolated_agents_sdk import isolated_agent, shared_state

@isolated_agent(working_dir="./workspace")
@shared_state(key="research_data")
@dependencies("langchain", "langchain-openai")
def researcher(topic: str):
    """Research and store in shared state."""
    from langchain_openai import ChatOpenAI
    from pathlib import Path
    import json
    
    llm = ChatOpenAI(model="gpt-4")
    research = llm.invoke(f"Research: {topic}")
    
    # Store in shared state
    data = {"topic": topic, "content": research.content}
    Path("/output/shared_state.json").write_text(json.dumps(data))
    return data

@isolated_agent(working_dir="./workspace")
@shared_state(key="research_data")
@dependencies("langchain", "langchain-openai")
def writer():
    """Read from shared state and write."""
    from langchain_openai import ChatOpenAI
    from pathlib import Path
    import json
    
    # Read from shared state
    data = json.loads(Path("/output/shared_state.json").read_text())
    
    llm = ChatOpenAI(model="gpt-4")
    article = llm.invoke(f"Write article about: {data['content']}")
    
    Path("/output/article.txt").write_text(article.content)
    return {"status": "written"}

# Execute with shared state
researcher("AI Safety")
result = writer()
print(f"Article: {result.artifacts['article.txt']}")
```

### Message Passing Pattern

Pass messages between agents:

```python
from isolated_agents_sdk import isolated_agent, message_queue

@isolated_agent(working_dir="./workspace")
@message_queue(queue="tasks")
@dependencies("langchain", "langchain-openai")
def producer(count: int):
    """Produce tasks for workers."""
    from pathlib import Path
    import json
    
    tasks = [{"id": i, "task": f"Process item {i}"} for i in range(count)]
    Path("/output/tasks.json").write_text(json.dumps(tasks))
    return {"produced": count}

@isolated_agent(working_dir="./workspace")
@message_queue(queue="tasks")
@dependencies("langchain", "langchain-openai")
def consumer():
    """Consume and process tasks."""
    from pathlib import Path
    import json
    
    tasks = json.loads(Path("/output/tasks.json").read_text())
    results = []
    
    for task in tasks:
        # Process task
        result = {"id": task["id"], "status": "completed"}
        results.append(result)
    
    Path("/output/results.json").write_text(json.dumps(results))
    return {"processed": len(results)}

# Execute producer-consumer
producer(10)
result = consumer()
print(f"Processed: {result.return_value['processed']} tasks")
```

---

## Error Handling in Compositions

### Retry Pattern

Automatically retry failed agents:

```python
from isolated_agents_sdk import isolated_agent, retry, fallback

@isolated_agent(working_dir="./workspace")
@retry(max_attempts=3, backoff=2.0)
@network(enabled=True)
@dependencies("requests")
def fetch_data(url: str):
    """Fetch data with automatic retry."""
    import requests
    from pathlib import Path
    
    response = requests.get(url, timeout=10)
    response.raise_for_status()
    
    Path("/output/data.txt").write_text(response.text)
    return {"status": "success", "size": len(response.text)}

# Automatically retries on failure
result = fetch_data("https://api.example.com/data")
```

### Fallback Pattern

Use fallback agents when primary fails:

```python
from isolated_agents_sdk import isolated_agent, fallback

@isolated_agent(working_dir="./workspace")
@network(enabled=True)
@dependencies("langchain", "langchain-openai")
def primary_agent(query: str):
    """Primary agent using GPT-4."""
    from langchain_openai import ChatOpenAI
    from pathlib import Path
    
    llm = ChatOpenAI(model="gpt-4")
    result = llm.invoke(query)
    Path("/output/result.txt").write_text(result.content)
    return {"model": "gpt-4"}

@isolated_agent(working_dir="./workspace")
@network(enabled=True)
@dependencies("langchain", "langchain-openai")
def fallback_agent(query: str):
    """Fallback agent using GPT-3.5."""
    from langchain_openai import ChatOpenAI
    from pathlib import Path
    
    llm = ChatOpenAI(model="gpt-3.5-turbo")
    result = llm.invoke(query)
    Path("/output/result.txt").write_text(result.content)
    return {"model": "gpt-3.5-turbo"}

@fallback(
    primary=primary_agent,
    fallback=fallback_agent
)
def resilient_agent(query: str):
    """Automatically falls back if primary fails."""
    pass

# Uses fallback if primary fails
result = resilient_agent("Explain AI Safety")
print(f"Used model: {result.return_value['model']}")
```

---

## Advanced Patterns

### Map-Reduce Pattern

Process data in parallel and aggregate results:

```python
from isolated_agents_sdk import isolated_agent, map_reduce

@isolated_agent(working_dir="./workspace")
@dependencies("langchain", "langchain-openai")
def mapper(chunk: str):
    """Map function to process chunks."""
    from langchain_openai import ChatOpenAI
    from pathlib import Path
    import hashlib
    
    llm = ChatOpenAI(model="gpt-4")
    result = llm.invoke(f"Summarize: {chunk}")
    
    # Save with unique ID
    chunk_id = hashlib.md5(chunk.encode()).hexdigest()[:8]
    Path(f"/output/chunk_{chunk_id}.txt").write_text(result.content)
    return {"chunk_id": chunk_id, "summary": result.content}

@isolated_agent(working_dir="./workspace")
@dependencies("langchain", "langchain-openai")
def reducer(summaries: list):
    """Reduce function to aggregate results."""
    from langchain_openai import ChatOpenAI
    from pathlib import Path
    
    combined = "\n\n".join([s["summary"] for s in summaries])
    
    llm = ChatOpenAI(model="gpt-4")
    final = llm.invoke(f"Create final summary from: {combined}")
    
    Path("/output/final_summary.txt").write_text(final.content)
    return {"status": "reduced", "chunks": len(summaries)}

@map_reduce(
    mapper=mapper,
    reducer=reducer,
    chunk_size=1000  # Characters per chunk
)
def process_large_document(document: str):
    """Automatically chunks, maps, and reduces."""
    pass

# Process large document
large_text = "..." * 10000  # Large document
result = process_large_document(large_text)
print(f"Final summary: {result.artifacts['final_summary.txt']}")
```

### Event-Driven Pattern

React to events from other agents:

```python
from isolated_agents_sdk import isolated_agent, event_driven

@isolated_agent(working_dir="./workspace")
@event_driven(emits=["data_ready", "error"])
@dependencies("langchain", "langchain-openai")
def data_processor(data: str):
    """Process data and emit events."""
    from pathlib import Path
    import json
    
    try:
        # Process data
        result = {"status": "success", "data": data}
        Path("/output/result.json").write_text(json.dumps(result))
        
        # Emit success event
        event = {"type": "data_ready", "payload": result}
        Path("/output/events.json").write_text(json.dumps([event]))
        return result
    except Exception as e:
        # Emit error event
        event = {"type": "error", "payload": str(e)}
        Path("/output/events.json").write_text(json.dumps([event]))
        raise

@isolated_agent(working_dir="./workspace")
@event_driven(listens=["data_ready"])
@dependencies("langchain", "langchain-openai")
def data_consumer():
    """React to data_ready events."""
    from pathlib import Path
    import json
    
    events = json.loads(Path("/output/events.json").read_text())
    
    for event in events:
        if event["type"] == "data_ready":
            # Process event
            data = event["payload"]
            Path("/output/consumed.txt").write_text(str(data))
    
    return {"consumed": len(events)}

# Execute event-driven workflow
data_processor("sample data")
result = data_consumer()
print(f"Consumed {result.return_value['consumed']} events")
```

---

## Composition Best Practices

### 1. **Keep Agents Focused**
- Each agent should have a single, well-defined responsibility
- Avoid creating monolithic agents that do too much
- Use composition to combine simple agents into complex workflows

### 2. **Handle Errors Gracefully**
- Use `@retry` for transient failures
- Use `@fallback` for alternative approaches
- Implement proper error propagation in chains

### 3. **Optimize Data Flow**
- Minimize data transfer between agents
- Use shared state for large datasets
- Consider parallel execution for independent tasks

### 4. **Monitor Performance**
- Use telemetry to track agent execution
- Identify bottlenecks in compositions
- Optimize critical paths

### 5. **Test Compositions**
- Test individual agents in isolation
- Test compositions with mock data
- Use integration tests for end-to-end workflows

---

## Summary

The Isolated Agents SDK provides powerful composability features:

1. **Sequential Composition** - Chain agents in order
2. **Parallel Composition** - Run agents concurrently
3. **Hierarchical Composition** - Manager-worker patterns
4. **Pipeline Composition** - ETL-style workflows
5. **Conditional Composition** - Branching logic
6. **Data Flow Patterns** - Shared state and message passing
7. **Error Handling** - Retry and fallback patterns
8. **Advanced Patterns** - Map-reduce and event-driven

These patterns enable you to build sophisticated multi-agent systems while maintaining isolation, security, and observability.

---

**Next Steps:**
- Review [MULTIMODAL_OUTPUTS.md](MULTIMODAL_OUTPUTS.md) for output format support
- See [DECORATORS.md](DECORATORS.md) for decorator details
- Check [FRAMEWORK_COMPATIBILITY.md](FRAMEWORK_COMPATIBILITY.md) for framework integration