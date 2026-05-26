"""Distributed agents using RabbitMQ Work Queue pattern.

This example demonstrates:
- Multiple worker agents processing tasks from a shared queue
- Load balancing across workers
- Task acknowledgment and reliability
- Durable queues for persistence

Prerequisites:
    - RabbitMQ server running (docker run -d -p 5672:5672 rabbitmq)
    - Or use CloudAMQP

Usage:
    # Terminal 1 - Start worker 1
    export RABBITMQ_HOST=localhost
    python examples/distributed/rabbitmq_work_queue.py worker

    # Terminal 2 - Start worker 2
    export RABBITMQ_HOST=localhost
    python examples/distributed/rabbitmq_work_queue.py worker

    # Terminal 3 - Start producer
    export RABBITMQ_HOST=localhost
    python examples/distributed/rabbitmq_work_queue.py producer
"""

import os
import sys
from pathlib import Path


def producer_agent():
    """Producer agent - sends tasks to RabbitMQ queue."""
    import pika
    import json
    import time
    from pathlib import Path

    print("🚀 Producer Agent Starting...")

    # Connect to RabbitMQ
    rabbitmq_host = os.environ.get("RABBITMQ_HOST", "localhost")
    rabbitmq_port = int(os.environ.get("RABBITMQ_PORT", "5672"))

    try:
        connection = pika.BlockingConnection(
            pika.ConnectionParameters(host=rabbitmq_host, port=rabbitmq_port)
        )
        channel = connection.channel()
        print(f"✓ Connected to RabbitMQ at {rabbitmq_host}:{rabbitmq_port}")
    except Exception as e:
        print(f"✗ Failed to connect to RabbitMQ: {e}")
        return

    # Declare durable queue
    queue_name = "task_queue"
    channel.queue_declare(queue=queue_name, durable=True)

    output_dir = Path("/output")
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n📤 Sending tasks to queue: {queue_name}")
    print("=" * 60)

    tasks_sent = 0

    # Send tasks
    for i in range(20):
        task = {
            "id": i,
            "type": "compute",
            "operation": "process_data",
            "data": f"Task {i}",
            "complexity": i % 5,  # 0-4 complexity levels
            "timestamp": time.time()
        }

        # Publish with persistence
        channel.basic_publish(
            exchange='',
            routing_key=queue_name,
            body=json.dumps(task),
            properties=pika.BasicProperties(
                delivery_mode=2,  # Make message persistent
            )
        )
        tasks_sent += 1

        print(f"✓ Task {i:2d} sent | Complexity: {task['complexity']} | Data: {task['data']}")

        time.sleep(0.5)

    print("=" * 60)
    print(f"✓ Sent {tasks_sent} tasks")

    connection.close()

    # Save summary
    summary = f"""Producer Agent Summary
=====================
Queue: {queue_name}
Tasks Sent: {tasks_sent}
RabbitMQ Server: {rabbitmq_host}:{rabbitmq_port}
Status: Completed
"""
    (output_dir / "producer_summary.txt").write_text(summary)
    print("\n✓ Summary saved to /output/producer_summary.txt")


def worker_agent():
    """Worker agent - processes tasks from RabbitMQ queue."""
    import pika
    import json
    import time
    from pathlib import Path
    import signal
    import sys
    import random

    print("🚀 Worker Agent Starting...")

    # Connect to RabbitMQ
    rabbitmq_host = os.environ.get("RABBITMQ_HOST", "localhost")
    rabbitmq_port = int(os.environ.get("RABBITMQ_PORT", "5672"))

    try:
        connection = pika.BlockingConnection(
            pika.ConnectionParameters(host=rabbitmq_host, port=rabbitmq_port)
        )
        channel = connection.channel()
        print(f"✓ Connected to RabbitMQ at {rabbitmq_host}:{rabbitmq_port}")
    except Exception as e:
        print(f"✗ Failed to connect to RabbitMQ: {e}")
        return

    # Declare durable queue
    queue_name = "task_queue"
    channel.queue_declare(queue=queue_name, durable=True)

    # Fair dispatch - don't give more than one message to a worker at a time
    channel.basic_qos(prefetch_count=1)

    output_dir = Path("/output")
    output_dir.mkdir(parents=True, exist_ok=True)

    worker_id = random.randint(1000, 9999)

    print(f"\n📥 Worker {worker_id} waiting for tasks from queue: {queue_name}")
    print("=" * 60)

    tasks_processed = 0
    results = []

    # Handle graceful shutdown
    shutdown_requested = False

    def signal_handler(signum, frame):
        nonlocal shutdown_requested
        shutdown_requested = True
        print(f"\n⚠ Worker {worker_id} shutdown requested...")

    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    def callback(ch, method, properties, body):
        nonlocal tasks_processed, shutdown_requested

        if shutdown_requested:
            ch.stop_consuming()
            return

        task = json.loads(body)

        print(f"✓ Task {task['id']:2d} received | Complexity: {task['complexity']} | Processing...")

        # Simulate processing time based on complexity
        processing_time = task['complexity'] * 0.5
        time.sleep(processing_time)

        # Process task
        result = {
            "task_id": task['id'],
            "worker_id": worker_id,
            "operation": task['operation'],
            "data": task['data'],
            "processing_time": processing_time,
            "status": "completed"
        }
        results.append(result)
        tasks_processed += 1

        print(f"  ✓ Task {task['id']:2d} completed in {processing_time:.1f}s")

        # Acknowledge task
        ch.basic_ack(delivery_tag=method.delivery_tag)

        # Stop after processing 10 tasks
        if tasks_processed >= 10:
            print(f"\n✓ Worker {worker_id} processed target number of tasks, stopping...")
            ch.stop_consuming()

    # Start consuming
    channel.basic_consume(queue=queue_name, on_message_callback=callback)

    try:
        channel.start_consuming()
    except KeyboardInterrupt:
        print(f"\n⚠ Worker {worker_id} interrupted by user")
        channel.stop_consuming()

    connection.close()

    print("=" * 60)
    print(f"✓ Worker {worker_id} processed {tasks_processed} tasks")

    # Save results
    results_text = "\n".join([
        f"Task {r['task_id']}: {r['data']} - {r['status']} in {r['processing_time']:.1f}s"
        for r in results
    ])
    (output_dir / f"worker_{worker_id}_results.txt").write_text(results_text)

    summary = f"""Worker Agent Summary
===================
Worker ID: {worker_id}
Queue: {queue_name}
Tasks Processed: {tasks_processed}
RabbitMQ Server: {rabbitmq_host}:{rabbitmq_port}
Status: Completed
"""
    (output_dir / f"worker_{worker_id}_summary.txt").write_text(summary)

    print(f"\n✓ Results saved to /output/worker_{worker_id}_results.txt")
    print(f"✓ Summary saved to /output/worker_{worker_id}_summary.txt")


if __name__ == "__main__":
    from isolated_agents_sdk import run_agent, Policy, NetworkPolicy

    if len(sys.argv) < 2:
        print("Usage: python rabbitmq_work_queue.py [producer|worker]")
        sys.exit(1)

    mode = sys.argv[1].lower()

    if mode not in ["producer", "worker"]:
        print("Error: Mode must be 'producer' or 'worker'")
        sys.exit(1)

    # Check RabbitMQ connection
    rabbitmq_host = os.environ.get("RABBITMQ_HOST", "localhost")
    rabbitmq_port = os.environ.get("RABBITMQ_PORT", "5672")

    print(f"\n{'='*60}")
    print("RabbitMQ Work Queue Agent Communication Example")
    print(f"{'='*60}")
    print(f"Mode: {mode.upper()}")
    print(f"RabbitMQ: {rabbitmq_host}:{rabbitmq_port}")
    print(f"{'='*60}\n")

    # Select agent
    agent_func = producer_agent if mode == "producer" else worker_agent

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
                allowed_endpoints=[f"{rabbitmq_host}:{rabbitmq_port}"]
            ),
            allowed_env_vars=["RABBITMQ_HOST", "RABBITMQ_PORT"],
            pip_packages=["pika"],
            timeout_seconds=180 if mode == "worker" else 60,
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
