# Isolated Agents SDK - Adapter Architecture Diagram

## Current Architecture (Before Adapters)

```
┌─────────────────────────────────────────────────────────────────┐
│                         Public API                               │
│  run_agent() / async_run_agent() / list_sessions()              │
└────────────────────────┬────────────────────────────────────────┘
                         │
         ┌───────────────┼───────────────┐
         │               │               │
         ▼               ▼               ▼
┌─────────────┐  ┌─────────────┐  ┌─────────────┐
│  Policy     │  │  Container  │  │   Agent     │
│  Validator  │  │ Provisioner │  │   Runner    │
└─────────────┘  └──────┬──────┘  └──────┬──────┘
                        │                │
                        │    ┌───────────┤
                        │    │           │
                        ▼    ▼           ▼
                 ┌──────────────┐  ┌──────────────┐
                 │   Podman     │  │    Output    │
                 │   CLI Calls  │  │  Collector   │
                 └──────────────┘  └──────┬───────┘
                                          │
                                          ▼
                                   ┌──────────────┐
                                   │  Filesystem  │
                                   │  Operations  │
                                   └──────────────┘

         ┌────────────────────────────────────────┐
         │        Session Manager                  │
         │  (Cleanup, Timeouts, Monitoring)       │
         └────────────────────────────────────────┘
                         │
                         ▼
                 ┌──────────────┐
                 │ Audit Logger │
                 │ (File/Stderr)│
                 └──────────────┘

PROBLEMS:
❌ Tight coupling to Podman
❌ Hard-coded filesystem storage
❌ Fixed audit logging backend
❌ Difficult to test
❌ Cannot swap implementations
```

## New Architecture (With Adapters)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                            Public API                                    │
│  run_agent() / async_run_agent() / configure_adapters()                │
└────────────────────────┬────────────────────────────────────────────────┘
                         │
                         ▼
                ┌─────────────────┐
                │ Adapter Factory │
                │   & Registry    │
                └────────┬────────┘
                         │
         ┌───────────────┼───────────────┬───────────────┐
         │               │               │               │
         ▼               ▼               ▼               ▼
┌─────────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
│ Policy Validator│ │  Container  │ │   Storage   │ │    Audit    │
│    Adapter      │ │   Runtime   │ │   Backend   │ │   Logger    │
│   Interface     │ │   Adapter   │ │   Adapter   │ │   Adapter   │
│                 │ │  Interface  │ │  Interface  │ │  Interface  │
└────────┬────────┘ └──────┬──────┘ └──────┬──────┘ └──────┬──────┘
         │                 │               │               │
    ┌────┴────┐       ┌────┴────┐     ┌────┴────┐     ┌────┴────┐
    │         │       │         │     │         │     │         │
    ▼         ▼       ▼         ▼     ▼         ▼     ▼         ▼
┌────────┐ ┌────┐ ┌──────┐ ┌──────┐ ┌────┐ ┌────┐ ┌────┐ ┌─────────┐
│Default │ │OPA │ │Podman│ │Docker│ │Local│ │ S3 │ │File│ │CloudWatch│
└────────┘ └────┘ └──────┘ └──────┘ └────┘ └────┘ └────┘ └─────────┘
                  ┌──────┐          ┌────┐ ┌────┐ ┌────┐
                  │ K8s  │          │Azure│ │GCS │ │ DB │
                  └──────┘          └────┘ └────┘ └────┘

BENEFITS:
✅ Pluggable container runtimes
✅ Flexible storage backends
✅ Multiple audit destinations
✅ Easy to test with mocks
✅ Runtime adapter switching
```

## Component Interaction Flow

### 1. Agent Execution Flow (with Adapters)

```
User Code
   │
   │ run_agent(agent, working_dir, policy)
   │
   ▼
┌──────────────────────────────────────────────────────────────┐
│                      Public API Layer                         │
│  • Validates inputs                                           │
│  • Loads configuration                                        │
│  • Initializes adapters via factory                          │
└───────────────────────────┬──────────────────────────────────┘
                            │
                            ▼
                   ┌─────────────────┐
                   │ Adapter Factory │
                   │  • Creates       │
                   │  • Configures    │
                   │  • Caches        │
                   └────────┬─────────┘
                            │
        ┌───────────────────┼───────────────────┐
        │                   │                   │
        ▼                   ▼                   ▼
┌───────────────┐  ┌────────────────┐  ┌────────────────┐
│Policy Validator│  │Container Runtime│  │ Audit Logger   │
│   Adapter      │  │    Adapter      │  │   Adapter      │
└───────┬────────┘  └────────┬────────┘  └────────┬───────┘
        │                    │                    │
        │ validate()         │ provision()        │ log_event()
        ▼                    ▼                    ▼
   ┌─────────┐         ┌──────────┐         ┌──────────┐
   │ Policy  │         │Container │         │  Audit   │
   │ Rules   │         │ Created  │         │  Events  │
   └─────────┘         └────┬─────┘         └──────────┘
                            │
                            ▼
                   ┌─────────────────┐
                   │  Agent Runner   │
                   │  • Injects code │
                   │  • Executes     │
                   │  • Monitors     │
                   └────────┬────────┘
                            │
                            ▼
                   ┌─────────────────┐
                   │Output Collector │
                   │  Uses Storage   │
                   │  Adapter        │
                   └────────┬────────┘
                            │
                            ▼
                   ┌─────────────────┐
                   │Storage Backend  │
                   │   Adapter       │
                   │ • store()       │
                   │ • retrieve()    │
                   └────────┬────────┘
                            │
                            ▼
                      ┌──────────┐
                      │ Artifacts│
                      │ Stored   │
                      └──────────┘
```

### 2. Adapter Selection Flow

```
Application Startup
        │
        ▼
┌────────────────────────────────────────┐
│  Configuration Loading                 │
│  1. Load YAML config file              │
│  2. Override with env variables        │
│  3. Apply programmatic config          │
└───────────────┬────────────────────────┘
                │
                ▼
        ┌───────────────┐
        │ Config Object │
        │  adapters:    │
        │   - container │
        │   - storage   │
        │   - audit     │
        │   - policy    │
        └───────┬───────┘
                │
                ▼
        ┌───────────────┐
        │Adapter Factory│
        └───────┬───────┘
                │
    ┌───────────┼───────────┐
    │           │           │
    ▼           ▼           ▼
┌────────┐ ┌────────┐ ┌────────┐
│Registry│ │Registry│ │Registry│
│Lookup  │ │Lookup  │ │Lookup  │
└───┬────┘ └───┬────┘ └───┬────┘
    │          │          │
    ▼          ▼          ▼
┌────────┐ ┌────────┐ ┌────────┐
│Adapter │ │Adapter │ │Adapter │
│Instance│ │Instance│ │Instance│
└────────┘ └────────┘ └────────┘
```

### 3. Multi-Adapter Scenario

```
┌─────────────────────────────────────────────────────────────┐
│                    Production Deployment                     │
│                                                              │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐ │
│  │   Region 1   │    │   Region 2   │    │   Region 3   │ │
│  │              │    │              │    │              │ │
│  │  Container:  │    │  Container:  │    │  Container:  │ │
│  │   Docker     │    │   Podman     │    │   K8s        │ │
│  │              │    │              │    │              │ │
│  │  Storage:    │    │  Storage:    │    │  Storage:    │ │
│  │   S3         │    │   Azure      │    │   GCS        │ │
│  │              │    │              │    │              │ │
│  │  Audit:      │    │  Audit:      │    │  Audit:      │ │
│  │   CloudWatch │    │   Database   │    │   Datadog    │ │
│  └──────────────┘    └──────────────┘    └──────────────┘ │
│                                                              │
│  All regions use the same SDK codebase with different       │
│  adapter configurations!                                     │
└─────────────────────────────────────────────────────────────┘
```

## Adapter Interface Hierarchy

```
┌─────────────────────────────────────────────────────────────┐
│                      BaseAdapter                             │
│  • Common lifecycle methods                                  │
│  • Configuration management                                  │
│  • Error handling                                            │
└────────────────────────┬────────────────────────────────────┘
                         │
         ┌───────────────┼───────────────┬───────────────┐
         │               │               │               │
         ▼               ▼               ▼               ▼
┌─────────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
│ContainerRuntime │ │   Storage   │ │    Audit    │ │   Policy    │
│    Adapter      │ │   Backend   │ │   Logger    │ │  Validator  │
│                 │ │   Adapter   │ │   Adapter   │ │   Adapter   │
├─────────────────┤ ├─────────────┤ ├─────────────┤ ├─────────────┤
│• provision()    │ │• store()    │ │• emit()     │ │• validate() │
│• exec()         │ │• retrieve() │ │• query()    │ │• enforce()  │
│• copy()         │ │• list()     │ │• flush()    │ │• check()    │
│• stats()        │ │• delete()   │ │             │ │             │
│• destroy()      │ │• get_url()  │ │             │ │             │
└─────────────────┘ └─────────────┘ └─────────────┘ └─────────────┘
```

## Configuration Cascade

```
┌─────────────────────────────────────────────────────────────┐
│                    Configuration Priority                    │
│                    (Highest to Lowest)                       │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
                    ┌──────────────────┐
                    │  1. Programmatic │
                    │  configure_      │
                    │  adapters()      │
                    └────────┬─────────┘
                             │
                             ▼
                    ┌──────────────────┐
                    │  2. Environment  │
                    │  Variables       │
                    │  ISOLATED_       │
                    │  AGENTS_*        │
                    └────────┬─────────┘
                             │
                             ▼
                    ┌──────────────────┐
                    │  3. Config File  │
                    │  isolated_       │
                    │  agents.yaml     │
                    └────────┬─────────┘
                             │
                             ▼
                    ┌──────────────────┐
                    │  4. Defaults     │
                    │  Built-in        │
                    │  adapters        │
                    └──────────────────┘
```

## Error Handling Flow

```
Adapter Operation
        │
        ▼
    ┌───────┐
    │Execute│
    └───┬───┘
        │
        ├─── Success ──────────────────────────────┐
        │                                          │
        └─── Failure                               │
             │                                     │
             ▼                                     │
    ┌─────────────────┐                          │
    │ Adapter-Specific│                          │
    │ Error Handling  │                          │
    └────────┬────────┘                          │
             │                                     │
             ├─── Retryable ──┐                   │
             │                │                   │
             └─── Fatal       │                   │
                  │           │                   │
                  │           ▼                   │
                  │    ┌──────────┐              │
                  │    │  Retry   │              │
                  │    │  Logic   │              │
                  │    └────┬─────┘              │
                  │         │                     │
                  │         ├─── Success ─────────┤
                  │         │                     │
                  │         └─── Max Retries      │
                  │              Exceeded         │
                  │              │                │
                  ▼              ▼                │
            ┌──────────────────────┐             │
            │  Wrap in SDK         │             │
            │  Exception           │             │
            │  • AdapterError      │             │
            │  • ContainerError    │             │
            │  • StorageError      │             │
            └──────────┬───────────┘             │
                       │                         │
                       ▼                         │
                ┌──────────────┐                │
                │ Audit Event  │                │
                │ (if possible)│                │
                └──────┬───────┘                │
                       │                         │
                       ▼                         ▼
                ┌──────────────────────────────────┐
                │  Return to Caller                │
                │  • Result (success)              │
                │  • Exception (failure)           │
                └──────────────────────────────────┘
```

## Testing Strategy Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                      Testing Pyramid                         │
└─────────────────────────────────────────────────────────────┘

                        ┌──────────┐
                        │   E2E    │
                        │  Tests   │
                        └────┬─────┘
                             │
                    ┌────────┴────────┐
                    │  Integration    │
                    │     Tests       │
                    └────────┬────────┘
                             │
                ┌────────────┴────────────┐
                │    Adapter Tests        │
                │  (Real Implementations) │
                └────────────┬────────────┘
                             │
            ┌────────────────┴────────────────┐
            │      Component Tests            │
            │   (Mocked Adapters)             │
            └────────────────┬────────────────┘
                             │
        ┌────────────────────┴────────────────────┐
        │           Unit Tests                    │
        │    (Individual Functions/Classes)       │
        └─────────────────────────────────────────┘

Test Coverage by Layer:
┌──────────────────┬──────────┬─────────────────────────┐
│ Layer            │ Coverage │ Focus                   │
├──────────────────┼──────────┼─────────────────────────┤
│ Unit Tests       │   90%+   │ Logic correctness       │
│ Component Tests  │   85%+   │ Integration points      │
│ Adapter Tests    │   80%+   │ Real implementations    │
│ Integration      │   70%+   │ End-to-end flows        │
│ E2E Tests        │   50%+   │ Production scenarios    │
└──────────────────┴──────────┴─────────────────────────┘
```

## Deployment Patterns

### Pattern 1: Single Environment

```
┌─────────────────────────────────────┐
│      Development Environment        │
│                                     │
│  Container: Podman (local)          │
│  Storage:   Local filesystem        │
│  Audit:     File (./audit.log)      │
│  Policy:    Default validator       │
└─────────────────────────────────────┘
```

### Pattern 2: Cloud-Native

```
┌─────────────────────────────────────┐
│      Production Environment         │
│                                     │
│  Container: Kubernetes (EKS)        │
│  Storage:   S3 (encrypted)          │
│  Audit:     CloudWatch Logs         │
│  Policy:    OPA (compliance rules)  │
└─────────────────────────────────────┘
```

### Pattern 3: Hybrid

```
┌─────────────────────────────────────┐
│      Hybrid Environment             │
│                                     │
│  Container: Docker (on-prem)        │
│  Storage:   Azure Blob (cloud)      │
│  Audit:     Database (on-prem)      │
│  Policy:    Custom validator        │
└─────────────────────────────────────┘
```

---

**Legend**:
- `┌─┐` = Component boundary
- `│` = Vertical connection
- `─` = Horizontal connection
- `▼` = Data/control flow
- `┬` = Split/branch point
- `┴` = Merge point