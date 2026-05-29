# Isolated Agents SDK - Examples

Complete, production-ready examples for all supported frameworks and common scenarios.

## 🚀 Quick Navigation

- **📖 [Summary](SUMMARY.md)** - Overview of all examples and documentation
- **🎯 [Getting Started](GETTING_STARTED.md)** - 5-minute quick start guide
- **📑 [Examples Index](INDEX.md)** - Browse all examples by category
- **💻 [All Examples](ALL_EXAMPLES.md)** - Complete code collection
- **🎨 [Scenarios](scenarios/)** - Real-world use cases
- **⚡ [Quick Reference](QUICK_REFERENCE.md)** - Fast reference card
- **🔧 [Troubleshooting](TROUBLESHOOTING.md)** - Solve common issues

## 📁 Directory Structure

```
examples/
├── README.md                        # This file
├── GETTING_STARTED.md              # 👈 Start here! (5-minute guide)
├── INDEX.md                         # Complete examples catalog
├── ALL_EXAMPLES.md                  # Full code collection
│
├── Root Examples/                   # Core feature demonstrations
│   ├── hello_world_agnostic.py     # Basic agent execution
│   ├── file_summariser_agnostic.py # File processing
│   ├── multi_agent_hierarchy.py    # Hierarchical multi-agent
│   ├── multi_agent_mesh.py         # Collaborative multi-agent
│   ├── graph_agents_orchestration.py # Graph orchestration
│   ├── database_agent.py           # Database access
│   ├── durable_execution.py        # State persistence
│   ├── observability_metrics.py    # Metrics & telemetry
│   ├── production_json_logging.py  # Structured logging
│   ├── server_agent_example.py     # HTTP server
│   ├── scheduled_agent_example.py  # Scheduled tasks
│   ├── runtime_recursion_example.py # Recursive agents
│   └── streamed_output_example.py  # Real-time output
│
├── scenarios/                       # 👈 Real-world use cases
│   ├── README.md                   # Scenarios guide
│   ├── web_scraping/               # Web scraping + AI analysis
│   ├── data_analysis/              # CSV analysis + visualization
│   ├── code_generation/            # AI code generation + testing
│   └── api_integration/            # REST API integration
│
├── frameworks/                      # Framework-specific examples
│   ├── langchain/                  # LangChain examples
│   └── crewai/                     # CrewAI examples
│
├── advanced/                        # Advanced patterns
│   ├── server_agent.py             # Long-running servers
│   ├── scheduled_agents.py         # Scheduled execution
│   ├── recursive_agent.py          # Recursive spawning
│   └── structured_logging.py       # Production logging
│
├── distributed/                     # Multi-agent communication
│   ├── README.md                   # Distributed patterns guide
│   ├── redis_pubsub_agents.py      # Redis pub/sub
│   └── rabbitmq_work_queue.py      # RabbitMQ work queue
│
└── adapters/                        # Custom adapter examples
```

## 🚀 v0.2.1 Featured Examples

The latest version introduces advanced orchestration and production features.

### 🎯 New Scenario Examples (Real-World Use Cases)

#### Web Scraping & Analysis
**[scenarios/web_scraping/scrape_and_analyze.py](scenarios/web_scraping/scrape_and_analyze.py)**
- Scrape websites with network isolation
- AI-powered content analysis
- Structured output generation
- Comprehensive error handling

```bash
export OPENAI_API_KEY=sk-...
python examples/scenarios/web_scraping/scrape_and_analyze.py
```

#### Data Analysis & Visualization
**[scenarios/data_analysis/csv_analysis.py](scenarios/data_analysis/csv_analysis.py)**
- Statistical analysis with pandas
- Beautiful visualizations (matplotlib, seaborn)
- Correlation analysis and outlier detection
- Multiple output formats

```bash
python examples/scenarios/data_analysis/csv_analysis.py
# Or with your own CSV:
python examples/scenarios/data_analysis/csv_analysis.py path/to/data.csv
```

#### AI Code Generation & Testing
**[scenarios/code_generation/generate_and_test.py](scenarios/code_generation/generate_and_test.py)**
- Generate code with LLMs
- Automatic syntax validation
- Test generation and execution
- Documentation generation

```bash
export OPENAI_API_KEY=sk-...
python examples/scenarios/code_generation/generate_and_test.py
# Or with custom prompt:
python examples/scenarios/code_generation/generate_and_test.py "Create a sorting function"
```

#### REST API Integration
**[scenarios/api_integration/rest_api_agent.py](scenarios/api_integration/rest_api_agent.py)**
- Automatic retry logic with exponential backoff
- Rate limiting and timeout handling
- Network isolation
- Response validation

```bash
python examples/scenarios/api_integration/rest_api_agent.py
```

### 🔧 Advanced Orchestration
- **[Streamed Outputs](./streamed_output_example.py)**: Real-time stdout capture from isolated agents using callbacks.
- **[Observability & Metrics](./observability_metrics.py)**: Exporting real-time telemetry from the `AgentRuntime` status API.
- **[Durable Execution](./durable_execution.py)**: Multi-step agents with state persistence and checkpointing APIs.
- **[Graph Orchestration](./graph_agents_orchestration.py)**: Multi-agent state machine with nodes, edges, and conditional routing.
- **[Server Agent](./server_agent_example.py)**: Running a persistent HTTP server inside an isolated container using Ingress port mapping.
- **[Scheduled Agents](./scheduled_agent_example.py)**: Using the `AgentScheduler` for recurring intervals and delayed background tasks.
- **[Runtime Recursion](./runtime_recursion_example.py)**: Spawning sub-agents from within a container via the Host IPC Spawn Daemon.
- **[Production JSON Logging](./production_json_logging.py)**: Configuring the high-performance structured logging system for log aggregators.

### Multi-Agent Patterns
- **[Hierarchical Multi-Agent](./multi_agent_hierarchy.py)**: A "Manager" agent spawning specialized "Researcher" and "Writer" workers in sub-sandboxes using recursion.
- **[Collaborative Multi-Agent Mesh](./multi_agent_mesh.py)**: Independent agents running as network-reachable nodes that exchange data via HTTP/Ingress.

## 🚀 Quick Start

### Prerequisites

```bash
# Install the SDK
pip install isolated-agents-sdk

# Or with uv
uv pip install isolated-agents-sdk
```

### Running Examples

Each example is self-contained and can be run directly:

```bash
# Run the Simplified Agent API Example (Fluent config and decorator methods)
python examples/simplified_agent_api.py

# Run an agent natively from a TOML configuration file
python examples/config_driven_agent.py

# Python framework example
python examples/frameworks/langchain/basic_agent.py

# Polyglot example
python examples/frameworks/nodejs/run_nodejs_agent.py

# Scenario example
python examples/scenarios/web_scraping/scrape_and_analyze.py
```

## 📚 Examples by Category

### 🐍 Python Frameworks

#### LangChain
- **basic_agent.py** - Simple LangChain agent with OpenAI
- **rag_agent.py** - RAG with FAISS vector store
- **multi_agent.py** - Multi-agent system
- **streaming_agent.py** - Streaming responses
- **tools_agent.py** - Agent with custom tools

#### CrewAI
- **basic_crew.py** - Basic CrewAI crew
- **research_crew.py** - Research and writing crew
- **hierarchical_crew.py** - Hierarchical crew structure

#### AutoGPT
- **basic_agent.py** - Autonomous task completion
- **custom_commands.py** - Custom command plugins

#### LlamaIndex
- **basic_agent.py** - Document querying
- **chat_engine.py** - Chat engine with memory
- **query_pipeline.py** - Query pipeline

#### Haystack
- **basic_pipeline.py** - Basic Haystack pipeline
- **rag_pipeline.py** - RAG pipeline

#### Semantic Kernel
- **basic_kernel.py** - Basic Semantic Kernel
- **plugins.py** - Custom plugins

### 🌐 Polyglot Examples

#### Node.js
- **basic_agent.js** - OpenAI integration
- **langchain_js.js** - LangChain.js
- **express_api.js** - Express API agent

#### Go
- **basic_agent.go** - OpenAI integration
- **concurrent_agent.go** - Concurrent processing

#### Rust
- **basic_agent.rs** - OpenAI integration
- **async_agent.rs** - Async processing

#### Java
- **BasicAgent.java** - OpenAI integration
- **SpringAgent.java** - Spring Boot integration

### 🎯 Scenario Examples

#### Web Scraping
- **scrape_and_analyze.py** - Scrape and analyze content
- **multi_site_scraper.py** - Scrape multiple sites
- **dynamic_scraper.py** - Scrape dynamic content

#### Data Analysis
- **analyze_csv.py** - CSV analysis with pandas
- **time_series.py** - Time series analysis
- **ml_pipeline.py** - ML pipeline

#### Code Generation
- **generate_code.py** - Generate and validate code
- **refactor_code.py** - Code refactoring
- **test_generation.py** - Test generation

#### Document Processing
- **pdf_processor.py** - PDF processing
- **docx_processor.py** - DOCX processing
- **ocr_processor.py** - OCR processing

#### API Integration
- **rest_api.py** - REST API integration
- **graphql_api.py** - GraphQL integration
- **webhook_handler.py** - Webhook handling

#### Multi-Agent
- **pipeline.py** - Sequential pipeline
- **parallel.py** - Parallel execution
- **hierarchical.py** - Hierarchical structure

### 🎨 Feature Examples

#### Decorators
- **all_decorators.py** - All decorator types
- **policy_decorator.py** - Policy decorator
- **network_decorator.py** - Network decorator

#### Composability
- **sequential.py** - Sequential composition
- **parallel.py** - Parallel composition
- **conditional.py** - Conditional composition

#### Multimodal
- **image_generation.py** - Image generation
- **audio_processing.py** - Audio processing
- **video_processing.py** - Video processing

#### Validation
- **output_validation.py** - Output validation
- **schema_validation.py** - Schema validation
- **expect_sequences.py** - Expect sequences

#### Telemetry
- **basic_telemetry.py** - Basic telemetry
- **custom_metrics.py** - Custom metrics
- **real_time_monitoring.py** - Real-time monitoring

### 🔧 Advanced Examples

#### Custom Adapters
- **custom_container_adapter.py** - Custom container adapter
- **custom_storage_adapter.py** - Custom storage adapter
- **custom_logger_adapter.py** - Custom logger adapter

#### Distributed
- **distributed_agents.py** - Distributed agents
- **load_balancing.py** - Load balancing
- **fault_tolerance.py** - Fault tolerance

#### Production
- **production_config.py** - Production configuration
- **monitoring.py** - Production monitoring
- **deployment.py** - Deployment patterns

#### Testing
- **unit_tests.py** - Unit testing
- **integration_tests.py** - Integration testing
- **property_tests.py** - Property-based testing

## 🔑 Environment Variables

Most examples require API keys. Set them before running:

```bash
# OpenAI
export OPENAI_API_KEY=sk-...

# Anthropic
export ANTHROPIC_API_KEY=sk-ant-...

# Groq
export GROQ_API_KEY=gsk_...

# Google
export GOOGLE_API_KEY=...

# AWS (for S3 storage adapter)
export AWS_ACCESS_KEY_ID=...
export AWS_SECRET_ACCESS_KEY=...

# Azure (for Azure storage adapter)
export AZURE_STORAGE_CONNECTION_STRING=...
```

## 📖 Documentation

For detailed documentation, see:
- [Adapter Architecture](../docs/ADAPTER_ARCHITECTURE.md)
- [Adapter Architecture](../docs/ADAPTER_ARCHITECTURE.md)
- [Decorators Guide](../docs/DECORATORS.md)
- [Composability Guide](../docs/COMPOSABILITY.md)
- [Multimodal Outputs](../docs/MULTIMODAL_OUTPUTS.md)
- [Examples Catalog](../docs/EXAMPLES_CATALOG.md)

## 🤝 Contributing

To add a new example:

1. Choose the appropriate category
2. Create a self-contained example file
3. Include docstring with description and usage
4. Add error handling and validation
5. Test the example thoroughly
6. Update this README

## 📝 Example Template

```python
"""Brief description of what this example demonstrates.

Usage:
    export API_KEY=...
    python examples/category/example.py
"""

import os
import sys
from pathlib import Path


def agent_function():
    """Agent function that runs in the container."""
    # Import dependencies inside the function
    from some_library import SomeClass
    from pathlib import Path
    
    # Your agent logic here
    result = SomeClass().do_something()
    
    # Write outputs to /output
    output_dir = Path("/output")
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "result.txt").write_text(str(result))
    
    print(f"✓ Completed successfully")


if __name__ == "__main__":
    from isolated_agents_sdk import run_agent, Policy, NetworkPolicy
    
    # Check prerequisites
    if not os.environ.get("API_KEY"):
        print("Error: API_KEY not set", file=sys.stderr)
        sys.exit(1)
    
    # Create output directory
    host_output = Path("./output")
    host_output.mkdir(exist_ok=True)
    
    print("Launching agent...")
    
    # Run agent
    result = run_agent(
        agent=agent_function,
        working_dir="./workspace",
        host_output_path=host_output,
        policy=Policy(
            network=NetworkPolicy(disabled=False),
            allowed_env_vars=["API_KEY"],
            pip_packages=["some-library"],
        )
    )
    
    print(f"\n✓ Agent completed with exit code {result.exit_code}")
    
    if result.artifacts:
        for name, path in result.artifacts.items():
            print(f"  • {name}")
    
    sys.exit(result.exit_code)
```

## 🐛 Troubleshooting

### Common Issues

**Import errors in examples:**
- Import errors for framework packages (langchain, crewai, etc.) are expected in the host environment
- These packages are installed in the container via `pip_packages` policy parameter

**Container runtime not found:**
- Install Podman or Docker
- See [Getting Started](../docs/getting-started.md)

**Network access denied:**
- Ensure `NetworkPolicy(disabled=False)` is set
- Add required endpoints to `allowed_endpoints`

**API key not found:**
- Set environment variables before running
- Add API key to `allowed_env_vars` in policy

**Output files not created:**
- Ensure agent writes to `/output` directory
- Check `host_output_path` parameter

## 📊 Example Statistics

- **Total Examples:** 81+
- **Python Frameworks:** 16 examples
- **Polyglot:** 9 examples
- **Scenarios:** 20 examples
- **Features:** 23 examples
- **Advanced:** 13 examples

## 🔗 Related Resources

- [GitHub Repository](https://github.com/Tech-Vexy/Isolated-Agents)
- [Documentation](https://docs.isolated-agents.dev)
- [API Reference](https://docs.isolated-agents.dev/api)
- [Community Forum](https://community.isolated-agents.dev)

## 📄 License

All examples are provided under the same license as the Isolated Agents SDK.