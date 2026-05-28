# Scenario-Based Examples

Real-world use cases demonstrating practical applications of the Isolated Agents SDK.

## Available Scenarios

### 🌐 Web Scraping
**Directory**: [`web_scraping/`](web_scraping/)

Extract and analyze content from websites safely.

**Examples**:
- [`scrape_and_analyze.py`](web_scraping/scrape_and_analyze.py) - Scrape websites and analyze content with AI

**Features**:
- HTTP requests with network isolation
- HTML parsing and content extraction
- AI-powered content analysis
- Structured output generation

**Usage**:
```bash
export OPENAI_API_KEY=sk-...
python examples/scenarios/web_scraping/scrape_and_analyze.py
```

---

### 📊 Data Analysis
**Directory**: [`data_analysis/`](data_analysis/)

Process and analyze data files with statistical methods and visualizations.

**Examples**:
- [`csv_analysis.py`](data_analysis/csv_analysis.py) - Comprehensive CSV analysis with visualizations

**Features**:
- CSV data processing
- Statistical analysis
- Data visualization (matplotlib, seaborn)
- Correlation analysis
- Outlier detection

**Usage**:
```bash
# Analyze sample data
python examples/scenarios/data_analysis/csv_analysis.py

# Analyze your own CSV
python examples/scenarios/data_analysis/csv_analysis.py path/to/your/data.csv
```

---

### 💻 Code Generation
**Directory**: [`code_generation/`](code_generation/)

Generate, validate, and test code using AI.

**Examples**:
- [`generate_and_test.py`](code_generation/generate_and_test.py) - AI-powered code generation with validation

**Features**:
- Code generation with LLMs
- Syntax validation (AST parsing)
- Automatic test generation
- Test execution and validation
- Documentation generation

**Usage**:
```bash
export OPENAI_API_KEY=sk-...

# Use default prompt
python examples/scenarios/code_generation/generate_and_test.py

# Custom prompt
python examples/scenarios/code_generation/generate_and_test.py "Create a function to sort a list"
```

---

### 🔌 API Integration
**Directory**: [`api_integration/`](api_integration/)

Integrate with external REST APIs safely and reliably.

**Examples**:
- [`rest_api_agent.py`](api_integration/rest_api_agent.py) - REST API integration with retry logic

**Features**:
- HTTP requests with authentication
- Automatic retry logic
- Rate limiting
- Error handling
- Response validation
- Network isolation

**Usage**:
```bash
# Works with public API (no key needed)
python examples/scenarios/api_integration/rest_api_agent.py

# With API key (if needed)
export API_KEY=your_key_here
python examples/scenarios/api_integration/rest_api_agent.py
```

---

## Common Patterns

### Pattern 1: Input/Output
All scenarios follow this pattern:
```python
def my_agent():
    # Read inputs from /workspace
    data = Path("/workspace/input.txt").read_text()
    
    # Process data
    result = process(data)
    
    # Write outputs to /output
    output_dir = Path("/output")
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "result.txt").write_text(result)
```

### Pattern 2: Error Handling
```python
try:
    # Your logic
    result = risky_operation()
except Exception as e:
    # Save error for debugging
    output_dir = Path("/output")
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "error.txt").write_text(str(e))
    raise
```

### Pattern 3: Network Access
```python
policy = Policy(
    network=NetworkPolicy(
        disabled=False,
        allowed_endpoints=["api.example.com:443"]
    )
)
```

### Pattern 4: Multiple Outputs
```python
# Save different formats
(output_dir / "data.json").write_text(json.dumps(data))
(output_dir / "report.md").write_text(markdown_report)
(output_dir / "summary.txt").write_text(summary)
(output_dir / "metadata.json").write_text(json.dumps(metadata))
```

## Scenario Comparison

| Scenario | Network | Packages | Complexity | Use Case |
|----------|---------|----------|------------|----------|
| Web Scraping | Required | requests, bs4, langchain | Medium | Content extraction |
| Data Analysis | Optional | pandas, matplotlib | Low | Data processing |
| Code Generation | Required | langchain, pytest | High | Code automation |
| API Integration | Required | requests | Medium | External services |

## Best Practices

### 1. Resource Limits
Set appropriate limits based on workload:
```python
policy = Policy(
    cpu_cores=2.0,      # CPU-intensive tasks
    memory_mb=2048,     # Data processing
    timeout_seconds=180 # Long-running tasks
)
```

### 2. Network Isolation
Always restrict network access:
```python
network=NetworkPolicy(
    disabled=False,
    allowed_endpoints=[
        "api.example.com:443",  # Specific endpoints only
        "cdn.example.com:443"
    ]
)
```

### 3. Error Handling
Always handle and log errors:
```python
try:
    result = agent_logic()
except Exception as e:
    # Log error
    print(f"Error: {e}")
    # Save for debugging
    (Path("/output") / "error.txt").write_text(str(e))
    raise
```

### 4. Output Organization
Organize outputs logically:
```
output/
├── data/           # Raw data
├── results/        # Processed results
├── visualizations/ # Charts and graphs
├── reports/        # Human-readable reports
└── metadata/       # Execution metadata
```

### 5. Progress Logging
Log progress for monitoring:
```python
print("Starting task...")
print(f"✓ Step 1 completed")
print(f"✓ Step 2 completed")
print(f"✓ Task completed successfully")
```

## Adding New Scenarios

To add a new scenario:

1. Create a new directory: `examples/scenarios/your_scenario/`
2. Create the main example file: `your_scenario_agent.py`
3. Follow the template structure:
   - Docstring with description and usage
   - Agent function with imports inside
   - Error handling
   - Multiple outputs
   - Main block with policy configuration
4. Add README.md explaining the scenario
5. Update this README with your scenario

## Template

```python
"""Brief description of the scenario.

This example demonstrates:
- Feature 1
- Feature 2
- Feature 3

Usage:
    python examples/scenarios/category/example.py
"""

import os
import sys
from pathlib import Path


def scenario_agent():
    """Agent function that runs in container."""
    from pathlib import Path
    import json
    
    print("Starting agent...")
    
    try:
        # Your logic here
        result = do_something()
        
        # Save outputs
        output_dir = Path("/output")
        output_dir.mkdir(parents=True, exist_ok=True)
        
        (output_dir / "result.json").write_text(json.dumps(result))
        
        print("✓ Completed successfully")
        return result
        
    except Exception as e:
        print(f"✗ Error: {e}")
        output_dir = Path("/output")
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "error.txt").write_text(str(e))
        raise


if __name__ == "__main__":
    from isolated_agents_sdk import run_agent, Policy
    
    output = Path("./output/scenario")
    output.mkdir(parents=True, exist_ok=True)
    
    policy = Policy(
        cpu_cores=2.0,
        memory_mb=2048,
        timeout_seconds=120,
        pip_packages=["package1", "package2"]
    )
    
    result = run_agent(
        agent=scenario_agent,
        working_dir="./workspace",
        host_output_path=output,
        policy=policy
    )
    
    sys.exit(result.exit_code)
```

## Next Steps

1. Try running the examples
2. Modify them for your use case
3. Combine multiple scenarios
4. Create your own scenarios
5. Share with the community

## Related Examples

- [Framework Examples](../frameworks/) - Framework-specific integrations
- [Advanced Examples](../advanced/) - Complex patterns
- [Distributed Examples](../distributed/) - Multi-agent systems

## Getting Help

- [Getting Started Guide](../GETTING_STARTED.md)
- [Full Documentation](../../docs/index.md)
- [GitHub Issues](https://github.com/Tech-Vexy/Isolated-Agents/issues)
