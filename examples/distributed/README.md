# Distributed Agent Communication Examples

This directory contains examples demonstrating agent-to-agent communication through message buses. These examples show how to build distributed systems where multiple isolated agents communicate asynchronously.

## Overview

Each example demonstrates a different message bus and communication pattern:

- **Redis Pub/Sub** - Publish/Subscribe pattern for broadcasting messages
- **RabbitMQ Work Queue** - Work queue pattern for load balancing tasks across workers

## Prerequisites

### Redis Example
```bash
# Start Redis server
docker run -d -p 6379:6379 redis

# Or use Redis Cloud (free tier available)
# Set REDIS_HOST environment variable
```

### RabbitMQ Example
```bash
# Start RabbitMQ server
docker run -d -p 5672:5672 rabbitmq

# Or use CloudAMQP (free tier available)
# Set RABBITMQ_HOST environment variable
```

## Examples

### 1. Redis Pub/Sub Pattern

**File:** [`redis_pubsub_agents.py`](redis_pubsub_agents.py)

**Pattern:** Publish/Subscribe
- Producer publishes messages to a channel
- Consumer(s) subscribe to the channel and receive all messages
- One-to-many communication
- Fire-and-forget messaging

**Usage:**
```bash
# Terminal 1 - Start consumer
export REDIS_HOST=localhost
python examples/distributed/redis_pubsub_agents.py consumer

# Terminal 2 - Start producer
export REDIS_HOST=localhost
python examples/distributed/redis_pubsub_agents.py producer
```

**Key Features:**
- ✓ Asynchronous message broadcasting
- ✓ Multiple subscribers supported
- ✓ Real-time message delivery
- ✓ Decoupled architecture
- ✓ Network isolation with allowed endpoints
- ✓ Automatic Redis package installation

**Output:**
```
Producer:
  output/producer/producer_summary.txt

Consumer:
  output/consumer/consumer_results.txt
  output/consumer/consumer_summary.txt
```

### 2. RabbitMQ Work Queue Pattern

**File:** [`rabbitmq_work_queue.py`](rabbitmq_work_queue.py)

**Pattern:** Work Queue (Task Queue)
- Producer sends tasks to a queue
- Multiple workers compete for tasks
- Load balancing across workers
- Task acknowledgment for reliability

**Usage:**
```bash
# Terminal 1 - Start worker 1
export RABBITMQ_HOST=localhost
python examples/distributed/rabbitmq_work_queue.py worker

# Terminal 2 - Start worker 2
export RABBITMQ_HOST=localhost
python examples/distributed/rabbitmq_work_queue.py worker

# Terminal 3 - Start producer
export RABBITMQ_HOST=localhost
python examples/distributed/rabbitmq_work_queue.py producer
```

**Key Features:**
- ✓ Load balancing across multiple workers
- ✓ Fair dispatch (one task per worker at a time)
- ✓ Task acknowledgment for reliability
- ✓ Durable queues (survive broker restart)
- ✓ Persistent messages
- ✓ Graceful shutdown handling
- ✓ Network isolation with allowed endpoints
- ✓ Automatic Pika package installation

**Output:**
```
Producer:
  output/producer/producer_summary.txt

Worker:
  output/worker/worker_<id>_results.txt
  output/worker/worker_<id>_summary.txt
```

## Architecture

### Communication Flow

```
┌─────────────────┐         ┌──────────────┐         ┌─────────────────┐
│  Producer       │         │  Message     │         │  Consumer/      │
│  Agent          │────────▶│  Bus         │────────▶│  Worker Agent   │
│  (Container 1)  │         │  (Redis/     │         │  (Container 2)  │
└─────────────────┘         │  RabbitMQ)   │         └─────────────────┘
                            └──────────────┘
```

### Isolation Model

Each agent runs in its own isolated container with:
- **Network Isolation**: Only allowed endpoints accessible
- **Filesystem Isolation**: Separate working directories
- **Process Isolation**: Independent execution environments
- **Resource Limits**: CPU, memory, and timeout constraints

### Security

All examples implement security best practices:
- Network policies restrict access to message bus only
- Environment variables for configuration (no hardcoded credentials)
- Graceful shutdown handling
- Error handling and connection validation

## Message Bus Comparison

| Feature | Redis Pub/Sub | RabbitMQ Work Queue |
|---------|---------------|---------------------|
| Pattern | Broadcast | Load Balancing |
| Delivery | Fire-and-forget | Acknowledged |
| Persistence | No | Yes (durable) |
| Ordering | No guarantee | FIFO per queue |
| Scalability | High | High |
| Complexity | Low | Medium |
| Use Case | Events, notifications | Task processing |

## Common Patterns

### 1. Pub/Sub (Redis)
- Broadcasting events to multiple subscribers
- Real-time notifications
- Event-driven architectures
- Monitoring and logging

### 2. Work Queue (RabbitMQ)
- Distributing tasks across workers
- Background job processing
- Load balancing
- Reliable task execution

### 3. Request/Reply
- Synchronous-style communication
- RPC-like patterns
- Service-to-service calls

### 4. Event Streaming
- Processing event streams
- Real-time analytics
- Data pipelines

## Best Practices

### 1. Connection Management
```python
# Always validate connections
try:
    client.ping()  # or equivalent
    print("✓ Connected")
except Exception as e:
    print(f"✗ Connection failed: {e}")
    return
```

### 2. Graceful Shutdown
```python
import signal

shutdown_requested = False

def signal_handler(signum, frame):
    global shutdown_requested
    shutdown_requested = True

signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)
```

### 3. Error Handling
```python
try:
    # Process message
    result = process(message)
    # Acknowledge
    channel.basic_ack(delivery_tag)
except Exception as e:
    # Reject and requeue
    channel.basic_nack(delivery_tag, requeue=True)
```

### 4. Network Policy
```python
policy = Policy(
    network=NetworkPolicy(
        disabled=False,
        allowed_endpoints=["message-bus:5672"]
    )
)
```

## Extending Examples

### Adding New Message Buses

To add support for Kafka, NATS, or other message buses:

1. Create new example file (e.g., `kafka_streaming.py`)
2. Implement producer and consumer agents
3. Add pip packages to policy
4. Update network policy with endpoints
5. Document usage and patterns

### Adding New Patterns

To implement additional patterns:

1. **Request/Reply**: Add correlation IDs and reply queues
2. **Event Streaming**: Add offset management and partitioning
3. **Priority Queues**: Use message priorities
4. **Dead Letter Queues**: Handle failed messages

## Troubleshooting

### Connection Issues
```bash
# Check if message bus is running
docker ps

# Check network connectivity
telnet localhost 6379  # Redis
telnet localhost 5672  # RabbitMQ
```

### Permission Issues
```bash
# Ensure output directory is writable
chmod 755 output/
```

### Package Installation
```bash
# Packages are installed automatically in containers
# To test locally:
pip install redis pika
```

## Additional Resources

- [Redis Documentation](https://redis.io/docs/)
- [RabbitMQ Tutorials](https://www.rabbitmq.com/getstarted.html)
- [Isolated Agents SDK Documentation](../../docs/index.md)
- [Agent Communication Guide](../../docs/AGENT_COMMUNICATION.md)

## Next Steps

1. Try running the examples
2. Modify message formats
3. Add more workers
4. Implement error handling
5. Add monitoring and metrics
6. Deploy to production

For more advanced patterns and production deployment, see the [Agent Communication Guide](../../docs/AGENT_COMMUNICATION.md).