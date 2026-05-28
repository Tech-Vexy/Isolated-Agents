# Examples Index

Complete catalog of all examples in the Isolated Agents SDK.

## 🚀 Quick Start

**New to Isolated Agents?** Start here:

1. **[Getting Started Guide](GETTING_STARTED.md)** - Learn the basics (5 minutes)
2. **[Hello World](hello_world_agnostic.py)** - Your first agent
3. **[File Processing](file_summariser_agnostic.py)** - Read and write files
4. **[Multi-Agent Pipeline](multi_agent_hierarchy.py)** - Chain multiple agents

## 📚 Examples by Category

### Beginner (Start Here)
Perfect for learning the basics.

| Example | Description | Time | Difficulty |
|---------|-------------|------|------------|
| [Hello World](hello_world_agnostic.py) | Basic agent execution | 2 min | ⭐ |
| [File Summarizer](file_summariser_agnostic.py) | Process text files | 3 min | ⭐ |
| [Streamed Output](streamed_output_example.py) | Real-time output capture | 5 min | ⭐ |

### Intermediate
Build practical applications.

| Example | Description | Time | Difficulty |
|---------|-------------|------|------------|
| [Web Scraping](scenarios/web_scraping/scrape_and_analyze.py) | Scrape and analyze websites | 10 min | ⭐⭐ |
| [Data Analysis](scenarios/data_analysis/csv_analysis.py) | Analyze CSV with visualizations | 10 min | ⭐⭐ |
| [API Integration](scenarios/api_integration/rest_api_agent.py) | REST API with retry logic | 10 min | ⭐⭐ |
| [Code Generation](scenarios/code_generation/generate_and_test.py) | AI-powered code generation | 15 min | ⭐⭐ |
| [Database Agent](database_agent.py) | Secure database access | 10 min | ⭐⭐ |

### Advanced
Complex patterns and architectures.

| Example | Description | Time | Difficulty |
|---------|-------------|------|------------|
| [Multi-Agent Hierarchy](multi_agent_hierarchy.py) | Manager-worker pattern | 15 min | ⭐⭐⭐ |
| [Multi-Agent Mesh](multi_agent_mesh.py) | Collaborative agents | 20 min | ⭐⭐⭐ |
| [Graph Orchestration](graph_agents_orchestration.py) | State machine workflow | 20 min | ⭐⭐⭐ |
| [Server Agent](server_agent_example.py) | Long-running HTTP server | 15 min | ⭐⭐⭐ |
| [Scheduled Agents](scheduled_agent_example.py) | Recurring background tasks | 15 min | ⭐⭐⭐ |
| [Runtime Recursion](runtime_recursion_example.py) | Agents spawning sub-agents | 20 min | ⭐⭐⭐ |
| [Durable Execution](durable_execution.py) | State persistence | 20 min | ⭐⭐⭐ |

### Production
Production-ready patterns.

| Example | Description | Time | Difficulty |
|---------|-------------|------|------------|
| [Production Logging](production_json_logging.py) | Structured logging | 10 min | ⭐⭐ |
| [Observability](observability_metrics.py) | Metrics and telemetry | 15 min | ⭐⭐⭐ |
| [Distributed Redis](distributed/redis_pubsub_agents.py) | Redis pub/sub | 20 min | ⭐⭐⭐ |
| [Distributed RabbitMQ](distributed/rabbitmq_work_queue.py) | RabbitMQ work queue | 20 min | ⭐⭐⭐ |

## 📁 Examples by Directory

### Root Examples
Core examples demonstrating key features.

```
examples/
├── hello_world_agnostic.py          # Basic agent execution
├── file_summariser_agnostic.py      # File processing
├── multi_agent_hierarchy.py         # Hierarchical multi-agent
├── multi_agent_mesh.py              # Collaborative multi-agent
├── graph_agents_orchestration.py    # Graph-based orchestration
├── database_agent.py                # Database access
├── durable_execution.py             # State persistence
├── observability_metrics.py         # Metrics and telemetry
├── production_json_logging.py       # Structured logging
├── server_agent_example.py          # HTTP server agent
├── scheduled_agent_example.py       # Scheduled tasks
├── runtime_recursion_example.py     # Recursive agents
└── streamed_output_example.py       # Real-time output
```

### Scenarios
Real-world use cases.

```
scenarios/
├── web_scraping/
│   └── scrape_and_analyze.py        # Web scraping + AI analysis
├── data_analysis/
│   └── csv_analysis.py              # CSV analysis + visualization
├── code_generation/
│   └── generate_and_test.py         # AI code generation + testing
└── api_integration/
    └── rest_api_agent.py            # REST API integration
```

### Frameworks
Framework-specific integrations.

```
frameworks/
├── langchain/                       # LangChain examples
├── crewai/                          # CrewAI examples
└── [more coming soon]
```

### Advanced
Complex patterns and techniques.

```
advanced/
├── server_agent.py                  # Long-running servers
├── scheduled_agents.py              # Scheduled execution
├── recursive_agent.py               # Recursive spawning
├── structured_logging.py            # Production logging
└── long_running_data_processor.py   # Long-running tasks
```

### Distributed
Multi-agent communication.

```
distributed/
├── redis_pubsub_agents.py          # Redis pub/sub pattern
├── rabbitmq_work_queue.py          # RabbitMQ work queue
└── README.md                        # Distributed patterns guide
```

## 🎯 Examples by Use Case

### AI & LLM Integration
- [Code Generation](scenarios/code_generation/generate_and_test.py) - Generate code with AI
- [Web Scraping + Analysis](scenarios/web_scraping/scrape_and_analyze.py) - AI-powered content analysis
- [File Summarizer](file_summariser_agnostic.py) - Summarize documents

### Data Processing
- [CSV Analysis](scenarios/data_analysis/csv_analysis.py) - Statistical analysis + visualization
- [Database Agent](database_agent.py) - SQL and NoSQL operations
- [File Processing](file_summariser_agnostic.py) - Text file processing

### Web & APIs
- [Web Scraping](scenarios/web_scraping/scrape_and_analyze.py) - Extract web content
- [REST API](scenarios/api_integration/rest_api_agent.py) - API integration
- [Server Agent](server_agent_example.py) - HTTP server

### Multi-Agent Systems
- [Hierarchical](multi_agent_hierarchy.py) - Manager-worker pattern
- [Mesh](multi_agent_mesh.py) - Peer-to-peer collaboration
- [Graph Orchestration](graph_agents_orchestration.py) - State machine workflow
- [Redis Pub/Sub](distributed/redis_pubsub_agents.py) - Message broadcasting
- [RabbitMQ Queue](distributed/rabbitmq_work_queue.py) - Task distribution

### Production & Operations
- [Observability](observability_metrics.py) - Metrics and monitoring
- [Structured Logging](production_json_logging.py) - Production logging
- [Scheduled Tasks](scheduled_agent_example.py) - Recurring execution
- [Durable Execution](durable_execution.py) - State persistence

## 🔍 Examples by Feature

### Network Access
Examples that use network connectivity:
- [Web Scraping](scenarios/web_scraping/scrape_and_analyze.py)
- [API Integration](scenarios/api_integration/rest_api_agent.py)
- [Code Generation](scenarios/code_generation/generate_and_test.py)
- [Server Agent](server_agent_example.py)
- [Redis Pub/Sub](distributed/redis_pubsub_agents.py)
- [RabbitMQ Queue](distributed/rabbitmq_work_queue.py)

### File I/O
Examples that read/write files:
- [File Summarizer](file_summariser_agnostic.py)
- [CSV Analysis](scenarios/data_analysis/csv_analysis.py)
- [Code Generation](scenarios/code_generation/generate_and_test.py)
- [Durable Execution](durable_execution.py)

### Database Access
Examples that use databases:
- [Database Agent](database_agent.py)

### Multi-Agent
Examples with multiple agents:
- [Multi-Agent Hierarchy](multi_agent_hierarchy.py)
- [Multi-Agent Mesh](multi_agent_mesh.py)
- [Graph Orchestration](graph_agents_orchestration.py)
- [Runtime Recursion](runtime_recursion_example.py)
- [Redis Pub/Sub](distributed/redis_pubsub_agents.py)
- [RabbitMQ Queue](distributed/rabbitmq_work_queue.py)

### Visualization
Examples that create visualizations:
- [CSV Analysis](scenarios/data_analysis/csv_analysis.py)

### Real-time Output
Examples with streaming output:
- [Streamed Output](streamed_output_example.py)
- [Observability](observability_metrics.py)

## 📖 Documentation

### Guides
- **[Getting Started](GETTING_STARTED.md)** - Learn the basics
- **[All Examples](ALL_EXAMPLES.md)** - Complete code collection
- **[Scenarios Guide](scenarios/README.md)** - Real-world use cases
- **[Distributed Guide](distributed/README.md)** - Multi-agent communication

### Reference
- **[Main README](README.md)** - Full examples catalog
- **[Project Documentation](../docs/index.md)** - Complete SDK docs
- **[API Reference](../docs/api/)** - API documentation

## 🎓 Learning Paths

### Path 1: Beginner to Intermediate (1-2 hours)
1. Read [Getting Started](GETTING_STARTED.md)
2. Run [Hello World](hello_world_agnostic.py)
3. Try [File Summarizer](file_summariser_agnostic.py)
4. Explore [Web Scraping](scenarios/web_scraping/scrape_and_analyze.py)
5. Build [Data Analysis](scenarios/data_analysis/csv_analysis.py)

### Path 2: Multi-Agent Systems (2-3 hours)
1. Start with [Multi-Agent Hierarchy](multi_agent_hierarchy.py)
2. Try [Multi-Agent Mesh](multi_agent_mesh.py)
3. Explore [Graph Orchestration](graph_agents_orchestration.py)
4. Learn [Redis Pub/Sub](distributed/redis_pubsub_agents.py)
5. Master [RabbitMQ Queue](distributed/rabbitmq_work_queue.py)

### Path 3: Production Deployment (2-3 hours)
1. Understand [Structured Logging](production_json_logging.py)
2. Implement [Observability](observability_metrics.py)
3. Setup [Scheduled Tasks](scheduled_agent_example.py)
4. Deploy [Server Agent](server_agent_example.py)
5. Add [Durable Execution](durable_execution.py)

### Path 4: AI & LLM Integration (1-2 hours)
1. Start with [File Summarizer](file_summariser_agnostic.py)
2. Try [Code Generation](scenarios/code_generation/generate_and_test.py)
3. Build [Web Scraping + Analysis](scenarios/web_scraping/scrape_and_analyze.py)
4. Explore framework examples in [frameworks/](frameworks/)

## 🛠️ Running Examples

### Prerequisites
```bash
# Install SDK
pip install isolated-agents-sdk

# Install container runtime (Podman or Docker)
podman --version  # or docker --version
```

### Basic Usage
```bash
# Run any example
python examples/example_name.py

# With environment variables
export OPENAI_API_KEY=sk-...
python examples/example_name.py

# With custom input
python examples/example_name.py path/to/input.csv
```

### Common Issues
- **Import errors**: Packages are installed in container, not host
- **Network errors**: Check `NetworkPolicy` configuration
- **Timeout errors**: Increase `timeout_seconds` in policy
- **Permission errors**: Ensure output directory is writable

See [Getting Started](GETTING_STARTED.md#troubleshooting) for more help.

## 📊 Statistics

- **Total Examples**: 25+
- **Beginner Examples**: 3
- **Intermediate Examples**: 6
- **Advanced Examples**: 8
- **Production Examples**: 4
- **Scenario Examples**: 4
- **Framework Examples**: 2+
- **Distributed Examples**: 2

## 🤝 Contributing

Want to add an example?

1. Choose appropriate directory
2. Follow the [template](scenarios/README.md#template)
3. Include comprehensive docstring
4. Add error handling
5. Test thoroughly
6. Update this index
7. Submit pull request

## 📝 License

All examples are provided under the same license as the Isolated Agents SDK (MIT).

## 🔗 Links

- [GitHub Repository](https://github.com/Tech-Vexy/Isolated-Agents)
- [Documentation](https://docs.isolated-agents.dev)
- [PyPI Package](https://pypi.org/project/isolated-agents-sdk/)
- [Issue Tracker](https://github.com/Tech-Vexy/Isolated-Agents/issues)
- [Discussions](https://github.com/Tech-Vexy/Isolated-Agents/discussions)

---

**Last Updated**: May 28, 2026
**SDK Version**: 0.2.1
