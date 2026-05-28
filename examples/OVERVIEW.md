# Examples Collection Overview

Visual guide to the Isolated Agents SDK examples.

## 🗺️ Navigation Map

```
START HERE
    ↓
📖 SUMMARY.md ────────────────┐
    ↓                         │
🎯 GETTING_STARTED.md         │
    ↓                         │
    ├─→ 🌟 Beginner           │
    │   └─→ hello_world       │
    │                         │
    ├─→ 🎨 Scenarios ←────────┤
    │   ├─→ Web Scraping      │
    │   ├─→ Data Analysis     │
    │   ├─→ Code Generation   │
    │   └─→ API Integration   │
    │                         │
    ├─→ 🚀 Advanced           │
    │   ├─→ Multi-Agent       │
    │   ├─→ Distributed       │
    │   └─→ Production        │
    │                         │
    └─→ 🔧 Need Help?         │
        ├─→ QUICK_REFERENCE   │
        └─→ TROUBLESHOOTING ──┘
```

## 📚 Documentation Structure

```
examples/
│
├── 📖 Core Documentation
│   ├── README.md              ← Main overview
│   ├── SUMMARY.md             ← Quick stats & overview
│   ├── GETTING_STARTED.md     ← Start here (5 min)
│   ├── INDEX.md               ← Complete catalog
│   ├── ALL_EXAMPLES.md        ← Full code collection
│   ├── QUICK_REFERENCE.md     ← Fast reference
│   ├── TROUBLESHOOTING.md     ← Problem solving
│   ├── IMPROVEMENTS.md        ← What's new
│   └── CHANGELOG.md           ← Version history
│
├── 🎨 Scenarios (Real-World Use Cases)
│   ├── README.md
│   ├── web_scraping/
│   │   └── scrape_and_analyze.py
│   ├── data_analysis/
│   │   └── csv_analysis.py
│   ├── code_generation/
│   │   └── generate_and_test.py
│   └── api_integration/
│       └── rest_api_agent.py
│
├── 🦜 Frameworks (Framework Integrations)
│   ├── README.md
│   ├── langchain/
│   │   ├── basic_agent.py
│   │   └── rag_agent.py
│   └── crewai/
│       └── basic_crew.py
│
├── 🚀 Advanced (Complex Patterns)
│   ├── server_agent.py
│   ├── scheduled_agents.py
│   ├── recursive_agent.py
│   └── structured_logging.py
│
├── 🌐 Distributed (Multi-Agent Communication)
│   ├── README.md
│   ├── redis_pubsub_agents.py
│   └── rabbitmq_work_queue.py
│
└── 🌟 Root Examples (Core Features)
    ├── hello_world_agnostic.py
    ├── file_summariser_agnostic.py
    ├── multi_agent_hierarchy.py
    ├── multi_agent_mesh.py
    ├── graph_agents_orchestration.py
    ├── database_agent.py
    ├── durable_execution.py
    ├── observability_metrics.py
    ├── production_json_logging.py
    ├── server_agent_example.py
    ├── scheduled_agent_example.py
    ├── runtime_recursion_example.py
    └── streamed_output_example.py
```

## 🎯 Choose Your Path

### 🌱 I'm New to Isolated Agents
```
1. Read GETTING_STARTED.md (5 min)
2. Run hello_world_agnostic.py
3. Try file_summariser_agnostic.py
4. Explore a scenario example
5. Check QUICK_REFERENCE.md
```

### 💼 I Want to Build Something
```
1. Browse scenarios/ directory
2. Pick a use case similar to yours
3. Copy and modify the example
4. Check TROUBLESHOOTING.md if stuck
5. Refer to QUICK_REFERENCE.md
```

### 🔬 I Want to Learn Advanced Patterns
```
1. Review INDEX.md for advanced examples
2. Start with multi_agent_hierarchy.py
3. Try distributed examples
4. Explore production patterns
5. Read framework integrations
```

### 🐛 I Have a Problem
```
1. Check TROUBLESHOOTING.md first
2. Review QUICK_REFERENCE.md
3. Look at similar examples
4. Check GitHub issues
5. Ask in discussions
```

## 📊 Examples by Complexity

```
Beginner (⭐)
├── hello_world_agnostic.py
├── file_summariser_agnostic.py
└── streamed_output_example.py

Intermediate (⭐⭐)
├── scenarios/web_scraping/
├── scenarios/data_analysis/
├── scenarios/api_integration/
├── scenarios/code_generation/
├── database_agent.py
└── frameworks/langchain/

Advanced (⭐⭐⭐)
├── multi_agent_hierarchy.py
├── multi_agent_mesh.py
├── graph_agents_orchestration.py
├── server_agent_example.py
├── scheduled_agent_example.py
├── runtime_recursion_example.py
├── durable_execution.py
├── distributed/redis_pubsub_agents.py
└── distributed/rabbitmq_work_queue.py

Production (⭐⭐⭐)
├── observability_metrics.py
├── production_json_logging.py
└── frameworks/crewai/
```

## 🎨 Examples by Use Case

### 🤖 AI & LLM
```
├── scenarios/code_generation/
├── scenarios/web_scraping/
├── file_summariser_agnostic.py
├── frameworks/langchain/
└── frameworks/crewai/
```

### 📊 Data Processing
```
├── scenarios/data_analysis/
├── database_agent.py
└── file_summariser_agnostic.py
```

### 🌐 Web & APIs
```
├── scenarios/web_scraping/
├── scenarios/api_integration/
└── server_agent_example.py
```

### 🔄 Multi-Agent
```
├── multi_agent_hierarchy.py
├── multi_agent_mesh.py
├── graph_agents_orchestration.py
├── runtime_recursion_example.py
├── distributed/redis_pubsub_agents.py
└── distributed/rabbitmq_work_queue.py
```

### 🏭 Production
```
├── observability_metrics.py
├── production_json_logging.py
├── scheduled_agent_example.py
└── durable_execution.py
```

## 🔧 Quick Commands

### Installation
```bash
pip install isolated-agents-sdk
```

### Run Examples
```bash
# Basic example
python examples/hello_world_agnostic.py

# With API key
export OPENAI_API_KEY=sk-...
python examples/scenarios/web_scraping/scrape_and_analyze.py

# With custom input
python examples/scenarios/data_analysis/csv_analysis.py data.csv
```

### Get Help
```bash
# Check container runtime
podman --version  # or docker --version

# View container logs
podman logs <container_id>

# List running containers
podman ps
```

## 📖 Documentation Quick Links

| Document | Purpose | Time |
|----------|---------|------|
| [SUMMARY.md](SUMMARY.md) | Overview & stats | 2 min |
| [GETTING_STARTED.md](GETTING_STARTED.md) | Quick start guide | 5 min |
| [INDEX.md](INDEX.md) | Browse all examples | 5 min |
| [QUICK_REFERENCE.md](QUICK_REFERENCE.md) | Fast reference | 2 min |
| [TROUBLESHOOTING.md](TROUBLESHOOTING.md) | Solve problems | As needed |
| [ALL_EXAMPLES.md](ALL_EXAMPLES.md) | Complete code | Reference |

## 🎓 Learning Paths

### Path 1: Beginner → Intermediate (1-2 hours)
```
GETTING_STARTED.md
    ↓
hello_world_agnostic.py
    ↓
file_summariser_agnostic.py
    ↓
scenarios/web_scraping/
    ↓
scenarios/data_analysis/
```

### Path 2: Multi-Agent Systems (2-3 hours)
```
multi_agent_hierarchy.py
    ↓
multi_agent_mesh.py
    ↓
graph_agents_orchestration.py
    ↓
distributed/redis_pubsub_agents.py
    ↓
distributed/rabbitmq_work_queue.py
```

### Path 3: Production Deployment (2-3 hours)
```
production_json_logging.py
    ↓
observability_metrics.py
    ↓
scheduled_agent_example.py
    ↓
server_agent_example.py
    ↓
durable_execution.py
```

## 🎯 Feature Matrix

| Example | Network | File I/O | Database | Multi-Agent | Visualization |
|---------|---------|----------|----------|-------------|---------------|
| hello_world | ❌ | ✅ | ❌ | ❌ | ❌ |
| web_scraping | ✅ | ✅ | ❌ | ❌ | ❌ |
| data_analysis | ❌ | ✅ | ❌ | ❌ | ✅ |
| code_generation | ✅ | ✅ | ❌ | ❌ | ❌ |
| api_integration | ✅ | ✅ | ❌ | ❌ | ❌ |
| database_agent | ❌ | ❌ | ✅ | ❌ | ❌ |
| multi_agent_hierarchy | ❌ | ❌ | ❌ | ✅ | ❌ |
| redis_pubsub | ✅ | ✅ | ❌ | ✅ | ❌ |
| observability | ❌ | ❌ | ❌ | ❌ | ❌ |

## 💡 Common Patterns

### Pattern 1: Basic Agent
```python
def agent():
    from pathlib import Path
    result = "Hello!"
    Path("/output/result.txt").write_text(result)
```

### Pattern 2: Network Request
```python
def agent():
    import requests
    response = requests.get("https://api.example.com")
    Path("/output/data.json").write_text(response.text)
```

### Pattern 3: Data Processing
```python
def agent():
    import pandas as pd
    df = pd.read_csv("/workspace/data.csv")
    summary = df.describe()
    Path("/output/summary.txt").write_text(summary.to_string())
```

### Pattern 4: Multi-Agent
```python
def manager():
    from isolated_agents_sdk.sub_agent_client import spawn_sub_agent
    result = spawn_sub_agent(agent=worker, policy=Policy())
    return result.output
```

## 🔗 External Resources

- **GitHub**: [Tech-Vexy/Isolated-Agents](https://github.com/Tech-Vexy/Isolated-Agents)
- **PyPI**: [isolated-agents-sdk](https://pypi.org/project/isolated-agents-sdk/)
- **Issues**: [Report Bug](https://github.com/Tech-Vexy/Isolated-Agents/issues)
- **Discussions**: [Ask Question](https://github.com/Tech-Vexy/Isolated-Agents/discussions)

## 📈 Statistics

- **Total Examples**: 25+
- **Documentation Files**: 9
- **Lines of Code**: ~3,000
- **Use Cases Covered**: 10+
- **Frameworks Supported**: 2+
- **Learning Paths**: 3

## 🎉 What's New in v2.0

✅ 7 new documentation files  
✅ 4 new scenario examples  
✅ 3 learning paths  
✅ Comprehensive troubleshooting  
✅ Quick reference card  
✅ 100% more code  
✅ Production-ready quality  

---

**Start Here**: [GETTING_STARTED.md](GETTING_STARTED.md)  
**Need Help**: [TROUBLESHOOTING.md](TROUBLESHOOTING.md)  
**Quick Ref**: [QUICK_REFERENCE.md](QUICK_REFERENCE.md)
