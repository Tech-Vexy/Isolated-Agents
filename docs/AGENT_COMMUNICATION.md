# Agent-to-Agent Communication

## Overview

The Isolated Agents SDK supports **distributed agent communication** through message buses, enabling:

- **Decoupled agents** - Agents deployed separately communicate asynchronously
- **Message buses** - Redis, RabbitMQ, Kafka, NATS, and custom buses
- **Pub/Sub patterns** - Publish-subscribe messaging
- **Request/Reply** - Synchronous-style communication over async buses
- **Event-driven** - React to events from other agents
- **Scalability** - Horizontal scaling of agent fleets

---

## Architecture

### Distributed Agent Communication

```
┌─────────────────┐         ┌─────────────────┐
│   Agent A       │         │   Agent B       │
│  (Container 1)  │         │  (Container 2)  │
│                 │         │                 │
│  ┌───────────┐  │         │  ┌───────────┐  │
│  │  Business │  │         │  │  Business │  │
│  │   Logic   │  │         │  │   Logic   │  │
│  └─────┬─────┘  │         │  └─────┬─────┘  │
│        │        │         │        │        │
│  ┌─────▼─────┐  │         │  ┌─────▼─────┐  │
│  │   Bus     │  │         │  │   Bus     │  │
│  │  Client   │  │         │  │  Client   │  │
│  └─────┬─────┘  │         │  └─────┬─────┘  │
└────────┼────────┘         └────────┼────────┘
         │                           │
         │    ┌─────────────────┐   │
         └────►  Message Bus    ◄───┘
              │  (Redis/Kafka)  │
              └─────────────────┘
```

### Communication Patterns

1. **Pub/Sub** - One-to-many broadcasting
2. **Request/Reply** - Synchronous-style RPC
3. **Work Queue** - Load balancing across agents
4. **Event Streaming** - Real-time event processing
5. **Topic-based** - Filtered message routing

---

## Supported Message Buses

### 1. Redis

**Best for:**
- Simple pub/sub
- Low latency
- Small to medium scale
- Caching + messaging

**Features:**
- Pub/Sub channels
- Streams
- Lists (queues)
- TTL support

### 2. RabbitMQ

**Best for:**
- Complex routing
- Guaranteed delivery
- Enterprise messaging
- AMQP protocol

**Features:**
- Exchanges and queues
- Routing keys
- Dead letter queues
- Message persistence

### 3. Apache Kafka

**Best for:**
- High throughput
- Event streaming
- Large scale
- Data pipelines

**Features:**
- Topics and partitions
- Consumer groups
- Replay capability
- Persistent logs

### 4. NATS

**Best for:**
- Cloud-native
- Microservices
- Low latency
- Simple deployment

**Features:**
- Subjects
- Queue groups
- JetStream persistence
- Request/Reply

### 5. Custom Buses

**Implement your own:**
- HTTP webhooks
- WebSockets
- gRPC
- Custom protocols

---

## Configuration

### Redis Bus

```python
from isolated_agents_sdk import Policy, NetworkPolicy

policy = Policy(
    network=NetworkPolicy(
        disabled=False,
        allowed_endpoints=[
            "redis.example.com:6379",  # Redis server
        ]
    ),
    allowed_env_vars=["REDIS_URL", "REDIS_PASSWORD"],
    pip_packages=["redis", "aioredis"],
)
```

### RabbitMQ Bus

```python
policy = Policy(
    network=NetworkPolicy(
        disabled=False,
        allowed_endpoints=[
            "rabbitmq.example.com:5672",  # AMQP
            "rabbitmq.example.com:15672",  # Management API
        ]
    ),
    allowed_env_vars=["RABBITMQ_URL"],
    pip_packages=["pika", "aio-pika"],
)
```

### Kafka Bus

```python
policy = Policy(
    network=NetworkPolicy(
        disabled=False,
        allowed_endpoints=[
            "kafka-1.example.com:9092",
            "kafka-2.example.com:9092",
            "kafka-3.example.com:9092",
        ]
    ),
    allowed_env_vars=["KAFKA_BROKERS"],
    pip_packages=["kafka-python", "aiokafka"],
)
```

---

## Examples

### Example 1: Redis Pub/Sub

#### Producer Agent

```python
"""Producer agent that publishes messages to Redis."""

from isolated_agents_sdk import run_agent, Policy, NetworkPolicy
from pathlib import Path
import os


def producer_agent():
    """Publish messages to Redis channel."""
    import redis
    import json
    import time
    from pathlib import Path
    
    # Connect to Redis
    r = redis.Redis(
        host=os.environ.get("REDIS_HOST", "localhost"),
        port=int(os.environ.get("REDIS_PORT", "6379")),
        password=os.environ.get("REDIS_PASSWORD"),
        decode_responses=True
    )
    
    output_dir = Path("/output")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Publish messages
    channel = "agent-events"
    messages_sent = 0
    
    for i in range(10):
        message = {
            "id": i,
            "type": "task",
            "data": f"Process item {i}",
            "timestamp": time.time()
        }
        
        # Publish to channel
        r.publish(channel, json.dumps(message))
        messages_sent += 1
        
        print(f"Published message {i} to {channel}")
        time.sleep(1)
    
    # Save summary
    (output_dir / "summary.txt").write_text(
        f"Published {messages_sent} messages to {channel}"
    )


if __name__ == "__main__":
    result = run_agent(
        agent=producer_agent,
        working_dir="./workspace",
        host_output_path="./output",
        policy=Policy(
            network=NetworkPolicy(
                disabled=False,
                allowed_endpoints=["localhost:6379"]
            ),
            allowed_env_vars=["REDIS_HOST", "REDIS_PORT", "REDIS_PASSWORD"],
            pip_packages=["redis"],
        )
    )
    
    print(f"Producer completed: {result.exit_code}")
```

#### Consumer Agent

```python
"""Consumer agent that subscribes to Redis channel."""

from isolated_agents_sdk import run_agent, Policy, NetworkPolicy
from pathlib import Path
import os


def consumer_agent():
    """Subscribe to Redis channel and process messages."""
    import redis
    import json
    from pathlib import Path
    
    # Connect to Redis
    r = redis.Redis(
        host=os.environ.get("REDIS_HOST", "localhost"),
        port=int(os.environ.get("REDIS_PORT", "6379")),
        password=os.environ.get("REDIS_PASSWORD"),
        decode_responses=True
    )
    
    output_dir = Path("/output")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Subscribe to channel
    pubsub = r.pubsub()
    channel = "agent-events"
    pubsub.subscribe(channel)
    
    print(f"Subscribed to {channel}, waiting for messages...")
    
    messages_received = 0
    results = []
    
    # Listen for messages (with timeout)
    for message in pubsub.listen():
        if message['type'] == 'message':
            data = json.loads(message['data'])
            
            # Process message
            result = f"Processed: {data['data']}"
            results.append(result)
            messages_received += 1
            
            print(f"Received message {data['id']}: {data['data']}")
            
            # Stop after 10 messages
            if messages_received >= 10:
                break
    
    # Save results
    (output_dir / "results.txt").write_text("\n".join(results))
    (output_dir / "summary.txt").write_text(
        f"Received {messages_received} messages from {channel}"
    )


if __name__ == "__main__":
    result = run_agent(
        agent=consumer_agent,
        working_dir="./workspace",
        host_output_path="./output",
        policy=Policy(
            network=NetworkPolicy(
                disabled=False,
                allowed_endpoints=["localhost:6379"]
            ),
            allowed_env_vars=["REDIS_HOST", "REDIS_PORT", "REDIS_PASSWORD"],
            pip_packages=["redis"],
            timeout_seconds=60,  # Timeout after 1 minute
        )
    )
    
    print(f"Consumer completed: {result.exit_code}")
```

### Example 2: RabbitMQ Work Queue

#### Worker Agent

```python
"""Worker agent that processes tasks from RabbitMQ queue."""

from isolated_agents_sdk import run_agent, Policy, NetworkPolicy
import os


def worker_agent():
    """Process tasks from RabbitMQ work queue."""
    import pika
    import json
    from pathlib import Path
    import time
    
    # Connect to RabbitMQ
    connection = pika.BlockingConnection(
        pika.URLParameters(os.environ["RABBITMQ_URL"])
    )
    channel = connection.channel()
    
    # Declare queue
    queue_name = "task-queue"
    channel.queue_declare(queue=queue_name, durable=True)
    
    output_dir = Path("/output")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    tasks_processed = 0
    results = []
    
    def callback(ch, method, properties, body):
        nonlocal tasks_processed
        
        task = json.loads(body)
        print(f"Processing task: {task['id']}")
        
        # Simulate work
        time.sleep(2)
        
        result = f"Completed task {task['id']}: {task['data']}"
        results.append(result)
        tasks_processed += 1
        
        # Acknowledge message
        ch.basic_ack(delivery_tag=method.delivery_tag)
        
        # Stop after 5 tasks
        if tasks_processed >= 5:
            ch.stop_consuming()
    
    # Start consuming
    channel.basic_qos(prefetch_count=1)
    channel.basic_consume(queue=queue_name, on_message_callback=callback)
    
    print(f"Worker waiting for tasks on {queue_name}...")
    channel.start_consuming()
    
    # Save results
    (output_dir / "results.txt").write_text("\n".join(results))
    (output_dir / "summary.txt").write_text(
        f"Processed {tasks_processed} tasks"
    )
    
    connection.close()


if __name__ == "__main__":
    result = run_agent(
        agent=worker_agent,
        working_dir="./workspace",
        host_output_path="./output",
        policy=Policy(
            network=NetworkPolicy(
                disabled=False,
                allowed_endpoints=["rabbitmq.example.com:5672"]
            ),
            allowed_env_vars=["RABBITMQ_URL"],
            pip_packages=["pika"],
            timeout_seconds=300,
        )
    )
    
    print(f"Worker completed: {result.exit_code}")
```

#### Task Publisher

```python
"""Publisher agent that sends tasks to RabbitMQ queue."""

from isolated_agents_sdk import run_agent, Policy, NetworkPolicy
import os


def publisher_agent():
    """Publish tasks to RabbitMQ work queue."""
    import pika
    import json
    from pathlib import Path
    
    # Connect to RabbitMQ
    connection = pika.BlockingConnection(
        pika.URLParameters(os.environ["RABBITMQ_URL"])
    )
    channel = connection.channel()
    
    # Declare queue
    queue_name = "task-queue"
    channel.queue_declare(queue=queue_name, durable=True)
    
    output_dir = Path("/output")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Publish tasks
    tasks_published = 0
    
    for i in range(10):
        task = {
            "id": i,
            "data": f"Task {i}",
            "priority": i % 3
        }
        
        channel.basic_publish(
            exchange='',
            routing_key=queue_name,
            body=json.dumps(task),
            properties=pika.BasicProperties(
                delivery_mode=2,  # Make message persistent
            )
        )
        
        tasks_published += 1
        print(f"Published task {i}")
    
    # Save summary
    (output_dir / "summary.txt").write_text(
        f"Published {tasks_published} tasks to {queue_name}"
    )
    
    connection.close()


if __name__ == "__main__":
    result = run_agent(
        agent=publisher_agent,
        working_dir="./workspace",
        host_output_path="./output",
        policy=Policy(
            network=NetworkPolicy(
                disabled=False,
                allowed_endpoints=["rabbitmq.example.com:5672"]
            ),
            allowed_env_vars=["RABBITMQ_URL"],
            pip_packages=["pika"],
        )
    )
    
    print(f"Publisher completed: {result.exit_code}")
```

### Example 3: Kafka Event Streaming

#### Event Producer

```python
"""Producer agent that streams events to Kafka."""

from isolated_agents_sdk import run_agent, Policy, NetworkPolicy
import os


def kafka_producer():
    """Stream events to Kafka topic."""
    from kafka import KafkaProducer
    import json
    from pathlib import Path
    import time
    
    # Create Kafka producer
    producer = KafkaProducer(
        bootstrap_servers=os.environ["KAFKA_BROKERS"].split(","),
        value_serializer=lambda v: json.dumps(v).encode('utf-8')
    )
    
    output_dir = Path("/output")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    topic = "agent-events"
    events_sent = 0
    
    # Stream events
    for i in range(100):
        event = {
            "id": i,
            "type": "sensor_reading",
            "value": i * 1.5,
            "timestamp": time.time()
        }
        
        # Send to Kafka
        future = producer.send(topic, value=event)
        future.get(timeout=10)  # Wait for confirmation
        
        events_sent += 1
        
        if (i + 1) % 10 == 0:
            print(f"Sent {i + 1} events")
        
        time.sleep(0.1)
    
    producer.flush()
    producer.close()
    
    # Save summary
    (output_dir / "summary.txt").write_text(
        f"Sent {events_sent} events to {topic}"
    )


if __name__ == "__main__":
    result = run_agent(
        agent=kafka_producer,
        working_dir="./workspace",
        host_output_path="./output",
        policy=Policy(
            network=NetworkPolicy(
                disabled=False,
                allowed_endpoints=[
                    "kafka-1.example.com:9092",
                    "kafka-2.example.com:9092",
                ]
            ),
            allowed_env_vars=["KAFKA_BROKERS"],
            pip_packages=["kafka-python"],
        )
    )
    
    print(f"Producer completed: {result.exit_code}")
```

#### Event Consumer

```python
"""Consumer agent that processes Kafka events."""

from isolated_agents_sdk import run_agent, Policy, NetworkPolicy
import os


def kafka_consumer():
    """Consume and process events from Kafka."""
    from kafka import KafkaConsumer
    import json
    from pathlib import Path
    
    # Create Kafka consumer
    consumer = KafkaConsumer(
        "agent-events",
        bootstrap_servers=os.environ["KAFKA_BROKERS"].split(","),
        value_deserializer=lambda m: json.loads(m.decode('utf-8')),
        group_id="agent-group",
        auto_offset_reset='earliest'
    )
    
    output_dir = Path("/output")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    events_processed = 0
    results = []
    
    # Process events
    for message in consumer:
        event = message.value
        
        # Process event
        result = f"Processed event {event['id']}: value={event['value']}"
        results.append(result)
        events_processed += 1
        
        if events_processed % 10 == 0:
            print(f"Processed {events_processed} events")
        
        # Stop after 100 events
        if events_processed >= 100:
            break
    
    consumer.close()
    
    # Save results
    (output_dir / "results.txt").write_text("\n".join(results))
    (output_dir / "summary.txt").write_text(
        f"Processed {events_processed} events"
    )


if __name__ == "__main__":
    result = run_agent(
        agent=kafka_consumer,
        working_dir="./workspace",
        host_output_path="./output",
        policy=Policy(
            network=NetworkPolicy(
                disabled=False,
                allowed_endpoints=[
                    "kafka-1.example.com:9092",
                    "kafka-2.example.com:9092",
                ]
            ),
            allowed_env_vars=["KAFKA_BROKERS"],
            pip_packages=["kafka-python"],
            timeout_seconds=300,
        )
    )
    
    print(f"Consumer completed: {result.exit_code}")
```

### Example 4: Request/Reply Pattern

```python
"""Request/Reply pattern using Redis."""

from isolated_agents_sdk import run_agent, Policy, NetworkPolicy
import os


def request_agent():
    """Send request and wait for reply."""
    import redis
    import json
    import uuid
    from pathlib import Path
    
    r = redis.Redis(
        host=os.environ.get("REDIS_HOST", "localhost"),
        decode_responses=True
    )
    
    output_dir = Path("/output")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Create request
    request_id = str(uuid.uuid4())
    request = {
        "id": request_id,
        "method": "calculate",
        "params": {"x": 10, "y": 20}
    }
    
    # Send request
    r.lpush("requests", json.dumps(request))
    print(f"Sent request {request_id}")
    
    # Wait for reply
    reply_key = f"reply:{request_id}"
    reply = r.brpop(reply_key, timeout=30)
    
    if reply:
        result = json.loads(reply[1])
        print(f"Received reply: {result}")
        
        (output_dir / "result.txt").write_text(
            f"Result: {result['result']}"
        )
    else:
        print("Timeout waiting for reply")


def reply_agent():
    """Process requests and send replies."""
    import redis
    import json
    from pathlib import Path
    
    r = redis.Redis(
        host=os.environ.get("REDIS_HOST", "localhost"),
        decode_responses=True
    )
    
    output_dir = Path("/output")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    requests_processed = 0
    
    # Process requests
    while requests_processed < 5:
        # Wait for request
        request_data = r.brpop("requests", timeout=30)
        
        if not request_data:
            break
        
        request = json.loads(request_data[1])
        print(f"Processing request {request['id']}")
        
        # Calculate result
        result = request['params']['x'] + request['params']['y']
        
        # Send reply
        reply = {
            "id": request['id'],
            "result": result
        }
        
        reply_key = f"reply:{request['id']}"
        r.lpush(reply_key, json.dumps(reply))
        r.expire(reply_key, 60)  # Expire after 1 minute
        
        requests_processed += 1
    
    (output_dir / "summary.txt").write_text(
        f"Processed {requests_processed} requests"
    )
```

---

## Best Practices

### 1. Use Connection Pooling

```python
# Reuse connections
connection_pool = redis.ConnectionPool(
    host='localhost',
    port=6379,
    max_connections=10
)

r = redis.Redis(connection_pool=connection_pool)
```

### 2. Handle Disconnections

```python
import time

def with_retry(func, max_retries=3):
    for attempt in range(max_retries):
        try:
            return func()
        except ConnectionError:
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)  # Exponential backoff
            else:
                raise
```

### 3. Use Message Schemas

```python
from dataclasses import dataclass
import json

@dataclass
class TaskMessage:
    id: str
    type: str
    data: dict
    
    def to_json(self):
        return json.dumps(self.__dict__)
    
    @classmethod
    def from_json(cls, data):
        return cls(**json.loads(data))
```

### 4. Implement Timeouts

```python
# Always use timeouts
message = r.brpop("queue", timeout=30)

# Or with context manager
with timeout(30):
    process_message()
```

### 5. Monitor Message Queues

```python
# Check queue depth
queue_length = r.llen("task-queue")
if queue_length > 1000:
    print("Warning: Queue backlog!")
```

### 6. Use Dead Letter Queues

```python
# RabbitMQ dead letter exchange
channel.queue_declare(
    queue='task-queue',
    arguments={
        'x-dead-letter-exchange': 'dlx',
        'x-message-ttl': 60000,  # 1 minute
    }
)
```

---

## Deployment Patterns

### Pattern 1: Microservices

```
Agent A (Service 1) ──► Redis ──► Agent B (Service 2)
                         │
                         └──────► Agent C (Service 3)
```

### Pattern 2: Event-Driven

```
Producer Agents ──► Kafka Topics ──► Consumer Agents
                                  └──► Stream Processors
```

### Pattern 3: Work Queue

```
Task Publishers ──► RabbitMQ Queue ──► Worker Pool
                                    (Multiple Agents)
```

### Pattern 4: Request/Reply

```
Client Agent ──► Request Queue ──► Server Agent
             ◄── Reply Queue ◄────
```

---

## Security Considerations

### 1. Authentication

```python
# Redis with password
r = redis.Redis(
    host='localhost',
    password=os.environ['REDIS_PASSWORD']
)

# RabbitMQ with credentials
connection = pika.BlockingConnection(
    pika.URLParameters(
        f"amqp://{user}:{password}@{host}:5672/"
    )
)
```

### 2. Encryption

```python
# Redis with TLS
r = redis.Redis(
    host='localhost',
    ssl=True,
    ssl_cert_reqs='required',
    ssl_ca_certs='/path/to/ca.crt'
)
```

### 3. Network Policies

```python
policy = Policy(
    network=NetworkPolicy(
        disabled=False,
        # Only allow specific message bus
        allowed_endpoints=["redis.internal:6379"]
    )
)
```

---

## Monitoring

### Metrics to Track

- **Message throughput** - Messages per second
- **Queue depth** - Backlog size
- **Processing time** - Time per message
- **Error rate** - Failed messages
- **Consumer lag** - Kafka consumer lag

### Example Monitoring

```python
import time

start_time = time.time()
messages_processed = 0

for message in consumer:
    process(message)
    messages_processed += 1
    
    # Log metrics every 100 messages
    if messages_processed % 100 == 0:
        elapsed = time.time() - start_time
        throughput = messages_processed / elapsed
        print(f"Throughput: {throughput:.2f} msg/s")
```

---

## Summary

The Isolated Agents SDK supports distributed agent communication through:

- ✅ **Multiple message buses** - Redis, RabbitMQ, Kafka, NATS
- ✅ **Communication patterns** - Pub/Sub, Request/Reply, Work Queue, Event Streaming
- ✅ **Decoupled deployment** - Agents deployed separately
- ✅ **Scalability** - Horizontal scaling of agent fleets
- ✅ **Security** - Network policies, authentication, encryption
- ✅ **Reliability** - Retries, dead letter queues, monitoring

For more information, see:
- [Long-Running Agents](LONG_RUNNING_AGENTS.md)
- [Composability](COMPOSABILITY.md)
- [Architecture](ADAPTER_ARCHITECTURE.md)