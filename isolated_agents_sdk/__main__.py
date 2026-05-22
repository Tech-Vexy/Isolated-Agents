"""CLI entry point for the Isolated Agents SDK Runtime."""

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path
from isolated_agents_sdk.runtime import AgentRuntime
from isolated_agents_sdk.models import Policy, NetworkPolicy
from isolated_agents_sdk.logging import setup_logging

async def run_runtime(args):
    """Start the agent runtime and keep it alive."""
    setup_logging(
        level=logging.DEBUG if args.debug else logging.INFO,
        structured=args.json
    )
    
    runtime = AgentRuntime(
        working_dir=args.workspace,
        runtime_id=args.id
    )
    
    print(f"--- Isolated Agents SDK Runtime v0.2.0 ---")
    print(f"ID: {runtime.runtime_id}")
    print(f"Workspace: {args.workspace}")
    
    try:
        await runtime.start()
        print(f"Runtime is active. Press Ctrl+C to stop.")
        
        # Keep alive
        while True:
            await asyncio.sleep(3600)
    except asyncio.CancelledError:
        print("\nShutting down runtime...")
    finally:
        await runtime.stop()
        print("Runtime stopped.")

async def run_one_liner(args):
    """Execute a one-liner agent sandbox."""
    # Use standard logging for one-liners to avoid JSON bundling unless requested
    setup_logging(level=logging.WARNING, structured=args.json)
    
    # Disable audit logs by default for a clean CLI output
    runtime = AgentRuntime(
        working_dir=args.workspace,
        enable_audit_logs=args.json
    )
    
    # Construct policy from CLI args
    policy = Policy(
        base_image=args.image,
        entrypoint=args.command.split() if args.command else None,
        memory_mb=args.memory,
        cpu_cores=args.cpu,
        network=NetworkPolicy(disabled=not args.network)
    )
    
    if args.env:
        for kv in args.env:
            if "=" in kv:
                k, v = kv.split("=", 1)
                policy.env_vars[k] = v

    try:
        await runtime.start()
        
        result = await runtime.run_agent(
            agent=None, # Use entrypoint
            policy=policy
        )
        
        if result.exit_code != 0:
            sys.exit(result.exit_code)
            
    finally:
        await runtime.stop()

def main():
    parser = argparse.ArgumentParser(description="Isolated Agents SDK CLI")
    subparsers = parser.add_subparsers(dest="subcommand", help="Subcommand to run")

    # 'runtime' command (legacy/default replacement)
    server_parser = subparsers.add_parser("runtime", help="Start the background agent runtime")
    server_parser.add_argument("--workspace", default="./runtime_workspace", help="Path to workspace")
    server_parser.add_argument("--id", help="Custom ID for this runtime")
    server_parser.add_argument("--json", action="store_true", help="Use structured JSON logging")
    server_parser.add_argument("--debug", action="store_true", help="Enable debug logging")

    # 'run' command (one-liners)
    run_parser = subparsers.add_parser("run", help="Run a one-liner agent sandbox")
    run_parser.add_argument("command", help="Command to run inside the container")
    run_parser.add_argument("--image", default="python:3.11-slim", help="Container image to use")
    run_parser.add_argument("--workspace", default="./tmp_workspace", help="Host workspace directory")
    run_parser.add_argument("--memory", type=int, default=512, help="Memory limit in MB")
    run_parser.add_argument("--cpu", type=float, default=1.0, help="CPU limit in cores")
    run_parser.add_argument("--network", action="store_true", help="Enable network access")
    run_parser.add_argument("--env", action="append", help="Environment variables (KEY=VAL)")
    run_parser.add_argument("--json", action="store_true", help="Use structured JSON logging")

    args = parser.parse_args()
    
    if args.subcommand == "run":
        asyncio.run(run_one_liner(args))
    elif args.subcommand == "runtime" or not args.subcommand:
        # Fallback to runtime mode if no subcommand (backward compat)
        asyncio.run(run_runtime(args))
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
