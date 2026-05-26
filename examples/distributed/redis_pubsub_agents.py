"""Distributed agents communicating via Redis Pub/Sub.

This example demonstrates:
- Two separate agents deployed independently
- Communication through Redis message bus
- Pub/Sub pattern
- Asynchronous message passing
- Decoupled architecture

Prerequisites:
    - Redis server running (docker run -d -p 6379:6379 redis)
    - Or use Redis Cloud

Usage:
    # Terminal 1 - Start consumer
    export REDIS_HOST=localhost
    python examples/distributed/redis_pubsub_agents.py consumer

    # Terminal 2 - Start producer
    export REDIS_HOST=localhost
    python examples/distributed/redis_pubsub_agents.py producer
"""

import os
import sys
from pathlib import Path


def producer_agent():
    """Producer agent - publishes messages to Redis channel."""
    import redis
    import json
    import time
    from pathlib import Path

    print("🚀 Producer Agent Starting...")

    # Connect to Redis
    redis_host = os.environ.get("REDIS_HOST", "localhost")
    redis_port = int(os.environ.get("REDIS_PORT", "6379"))

    r = redis.Redis(
        host=redis_host,
        port=redis_port,
        decode_responses=True
    )

    # Test connection
    try:
        r.ping()
        print(f"✓ Connected to Redis at {redis_host}:{redis_port}")
    except redis.ConnectionError as e:
        print(f"✗ Failed to connect to Redis: {e}")
        return

    output_dir = Path("/output")
    output_dir.mkdir(parents=True, exist_ok=True)

    # Publish messages
    channel = "agent-communication"
    messages_sent = 0

    print(f"\n📤 Publishing messages to channel: {channel}")
    print("=" * 60)

    for i in range(10):
        message = {
            "id": i,
            "type": "task",
            "action": "process",
            "data": f"Item {i}",
            "priority": i % 3,
            "timestamp": time.time()
        }

        # Publish to channel
        subscribers = r.publish(channel, json.dumps(message))
        messages_sent += 1

        print(f"✓ Message {i:2d} published | Subscribers: {subscribers} | Data: {message['data']}")

        time.sleep(1)

    print("=" * 60)
    print(f"✓ Published {messages_sent} messages")

    # Save summary
    summary = f"""Producer Agent Summary
=====================
Channel: {channel}
Messages Published: {messages_sent}
Redis Server: {redis_host}:{redis_port}
Status: Completed
"""
    (output_dir / "producer_summary.txt").write_text(summary)
    print("\n✓ Summary saved to /output/producer_summary.txt")


def consumer_agent():
    """Consumer agent - subscribes to Redis channel."""
    import redis
    import json
    from pathlib import Path
    import signal
    import sys

    print("🚀 Consumer Agent Starting...")

    # Connect to Redis
    redis_host = os.environ.get("REDIS_HOST", "localhost")
    redis_port = int(os.environ.get("REDIS_PORT", "6379"))

    r = redis.Redis(
        host=redis_host,
        port=redis_port,
        decode_responses=True
    )

    # Test connection
    try:
        r.ping()
        print(f"✓ Connected to Redis at {redis_host}:{redis_port}")
    except redis.ConnectionError as e:
        print(f"✗ Failed to connect to Redis: {e}")
        return

    output_dir = Path("/output")
    output_dir.mkdir(parents=True, exist_ok=True)

    # Subscribe to channel
    pubsub = r.pubsub()
    channel = "agent-communication"
    pubsub.subscribe(channel)

    print(f"\n📥 Subscribed to channel: {channel}")
    print("⏳ Waiting for messages...")
    print("=" * 60)

    messages_received = 0
    results = []

    # Handle graceful shutdown
    shutdown_requested = False

    def signal_handler(signum, frame):
        nonlocal shutdown_requested
        shutdown_requested = True
        print("\n⚠ Shutdown requested...")

    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    # Listen for messages
    try:
        for message in pubsub.listen():
            if shutdown_requested:
                break

            if message['type'] == 'message':
                data = json.loads(message['data'])

                # Process message
                result = {
                    "message_id": data['id'],
                    "action": data['action'],
                    "data": data['data'],
                    "status": "processed"
                }
                results.append(result)
                messages_received += 1

                print(f"✓ Message {data['id']:2d} received  | Priority: {data['priority']} | Data: {data['data']}")

                # Stop after 10 messages
                if messages_received >= 10:
                    print("\n✓ Received target number of messages, stopping...")
                    break

    except KeyboardInterrupt:
        print("\n⚠ Interrupted by user")

    finally:
        pubsub.unsubscribe()
        pubsub.close()

    print("=" * 60)
    print(f"✓ Received {messages_received} messages")

    # Save results
    results_text = "\n".join([
        f"Message {r['message_id']}: {r['data']} - {r['status']}"
        for r in results
    ])
    (output_dir / "consumer_results.txt").write_text(results_text)

    summary = f"""Consumer Agent Summary
=====================
Channel: {channel}
Messages Received: {messages_received}
Redis Server: {redis_host}:{redis_port}
Status: Completed
"""
    (output_dir / "consumer_summary.txt").write_text(summary)

    print("\n✓ Results saved to /output/consumer_results.txt")
    print("✓ Summary saved to /output/consumer_summary.txt")


if __name__ == "__main__":
    from isolated_agents_sdk import run_agent, Policy, NetworkPolicy

    if len(sys.argv) < 2:
        print("Usage: python redis_pubsub_agents.py [producer|consumer]")
        sys.exit(1)

    mode = sys.argv[1].lower()

    if mode not in ["producer", "consumer"]:
        print("Error: Mode must be 'producer' or 'consumer'")
        sys.exit(1)

    # Check Redis connection
    redis_host = os.environ.get("REDIS_HOST", "localhost")
    redis_port = os.environ.get("REDIS_PORT", "6379")

    print(f"\n{'='*60}")
    print("Redis Pub/Sub Agent Communication Example")
    print(f"{'='*60}")
    print(f"Mode: {mode.upper()}")
    print(f"Redis: {redis_host}:{redis_port}")
    print(f"{'='*60}\n")

    # Select agent
    agent_func = producer_agent if mode == "producer" else consumer_agent

    # Create output directory
    output = Path(f"./output/{mode}")
    output.mkdir(parents=True, exist_ok=True)

    # Run agent in isolated container
    result = run_agent(
        agent=agent_func,
        working_dir="./workspace",
        host_output_path=output,
        policy=Policy(
            network=NetworkPolicy(
                disabled=False,
                allowed_endpoints=[f"{redis_host}:{redis_port}"]
            ),
            allowed_env_vars=["REDIS_HOST", "REDIS_PORT"],
            pip_packages=["redis"],
            timeout_seconds=120 if mode == "consumer" else 60,
        )
    )

    print(f"\n{'='*60}")
    print(f"{mode.upper()} Agent completed with exit code: {result.exit_code}")
    print(f"{'='*60}")

    if result.artifacts:
        print("\nOutput artifacts:")
        for name, path in result.artifacts.items():
            size = Path(path).stat().st_size
            print(f"  • {name} ({size:,} bytes)")

            # Display summary
            if "summary" in name:
                print(f"\n{Path(path).read_text()}")

    sys.exit(result.exit_code)

# Made with Bob
