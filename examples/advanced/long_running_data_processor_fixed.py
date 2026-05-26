"""Long-running data processing agent (Fixed for Windows and Network).

This example demonstrates:
- Extended timeout configuration
- Progress tracking
- Resource monitoring
- Graceful shutdown handling
- Batch processing

Usage:
    python examples/advanced/long_running_data_processor_fixed.py
"""

import os
import sys
from pathlib import Path
import pandas as pd
import numpy as np


def create_sample_data():
    """Create sample dataset for processing."""
    workspace = Path("./workspace")
    workspace.mkdir(exist_ok=True)

    # Create large dataset (10,000 rows)
    data = {
        'id': range(10000),
        'value': np.random.randn(10000),
        'category': np.random.choice(['A', 'B', 'C', 'D'], 10000),
    }
    df = pd.DataFrame(data)
    df.to_csv(workspace / "large_dataset.csv", index=False)
    print(f"[OK] Created sample dataset with {len(df)} rows")


def data_processor():
    """Process large dataset over extended period."""
    import pandas as pd
    from pathlib import Path
    import time
    import signal
    import sys

    shutdown_requested = False

    def signal_handler(signum, frame):
        nonlocal shutdown_requested
        shutdown_requested = True
        print("\n[WARN] Shutdown requested, finishing current batch...")

    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    output_dir = Path("/output")
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        # Load large dataset
        data_path = Path("/workspace/large_dataset.csv")
        print(f"Loading dataset from {data_path}...")
        df = pd.read_csv(data_path)

        total_rows = len(df)
        batch_size = 500
        print(f"Processing {total_rows} rows in batches of {batch_size}")

        results = []
        processed_count = 0

        # Process in batches
        for i in range(0, total_rows, batch_size):
            if shutdown_requested:
                print(f"Stopping at batch {i//batch_size + 1}")
                break

            batch = df.iloc[i:i+batch_size]

            # Simulate processing (calculate statistics)
            processed = batch.groupby('category')['value'].agg(['mean', 'std', 'count'])
            results.append(processed)

            processed_count += len(batch)

            # Report progress
            progress = min(processed_count / total_rows * 100, 100)
            (output_dir / "progress.txt").write_text(f"{progress:.1f}%")

            # Log progress every 10 batches
            batch_num = i // batch_size + 1
            if batch_num % 10 == 0:
                print(f"[OK] Processed {processed_count}/{total_rows} rows ({progress:.1f}%)")

            # Simulate processing time
            time.sleep(0.5)

        # Aggregate results
        if results:
            result_df = pd.concat(results)
            final_stats = result_df.groupby(level=0).mean()

            # Save results
            final_stats.to_csv(output_dir / "processed_data.csv")

            summary = f"""Processing Summary
==================
Total rows: {total_rows}
Processed rows: {processed_count}
Batches: {len(results)}
Status: {'Interrupted' if shutdown_requested else 'Completed'}

Statistics by Category:
{final_stats.to_string()}
"""
            (output_dir / "summary.txt").write_text(summary)

            print(f"\n[OK] Processing {'interrupted' if shutdown_requested else 'completed'}")
            print(f"[OK] Processed {processed_count}/{total_rows} rows")

    except Exception as e:
        error_msg = f"Error during processing: {str(e)}"
        (output_dir / "error.txt").write_text(error_msg)
        print(f"[FAIL] {error_msg}")
        raise

    finally:
        # Cleanup
        print("[OK] Cleanup completed")


if __name__ == "__main__":
    from isolated_agents_sdk import run_agent, Policy, NetworkPolicy

    # Create sample data
    create_sample_data()

    output = Path("./output")
    output.mkdir(exist_ok=True)

    print("\nLaunching long-running data processor...")
    print("Press Ctrl+C to test graceful shutdown\n")

    # Run with extended timeout and resource monitoring
    # ENABLE NETWORK so pip can install packages!
    result = run_agent(
        agent=data_processor,
        working_dir="./workspace",
        host_output_path=output,
        policy=Policy(
            timeout_seconds=3600,  # 1 hour timeout
            cpu_cores=2.0,
            memory_mb=2048,
            network=NetworkPolicy(disabled=False), # Allow network for pip
            resource_monitor_interval=30,  # Check resources every 30s
            cpu_threshold_percent=85.0,
            memory_threshold_percent=85.0,
            pip_packages=["pandas", "numpy", "python-dateutil", "pytz", "six"],
        )
    )

    print(f"\n{'='*60}")
    print(f"Agent completed with exit code: {result.exit_code}")

    if result.artifacts:
        print("\nOutput artifacts:")
        for name, path in result.artifacts.items():
            size = Path(path).stat().st_size
            print(f"  * {name} ({size:,} bytes)")

        # Display summary
        summary_path = result.artifacts.get("summary.txt")
        if summary_path:
            print(f"\n{Path(summary_path).read_text()}")

    sys.exit(result.exit_code)
