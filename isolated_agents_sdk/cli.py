"""Command-line interface for Isolated Agents SDK.

This module provides a CLI tool for managing and running isolated agents
without writing Python code.

Usage:
    # Initialize new project
    isolated-agents init my-project
    
    # Create default config
    isolated-agents config create
    
    # List agents in config
    isolated-agents config list
    
    # Run agent from config
    isolated-agents run data_processor
    
    # List running agents
    isolated-agents ps
    
    # View agent logs
    isolated-agents logs <session-id>
    
    # Stop agent
    isolated-agents stop <session-id>
    
    # Clean up resources
    isolated-agents cleanup
"""

import argparse
import sys
from pathlib import Path
from typing import Optional


def cmd_init(args):
    """Initialize a new project."""
    project_name = args.name
    project_dir = Path(project_name)
    
    if project_dir.exists():
        print(f"Error: Directory '{project_name}' already exists", file=sys.stderr)
        return 1
    
    # Create project structure
    project_dir.mkdir(parents=True)
    (project_dir / "workspace").mkdir()
    (project_dir / "output").mkdir()
    
    # Create default config
    from isolated_agents_sdk.config import create_default_config
    config_path = project_dir / "isolated-agents.yaml"
    create_default_config(config_path)
    
    # Create example agent
    example_agent = '''"""Example agent for Isolated Agents SDK."""

from pathlib import Path


def example_agent():
    """Simple example agent."""
    from pathlib import Path
    
    # Your agent logic here
    result = "Hello from isolated agent!"
    
    # Write output
    output_dir = Path("/output")
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "result.txt").write_text(result)
    
    print(f"✓ Agent completed: {result}")
    return result


if __name__ == "__main__":
    from isolated_agents_sdk import Agent
    
    agent = Agent(example_agent, workspace="./workspace")
    result = agent.run(output="./output")
    
    print(f"Exit code: {result.exit_code}")
'''
    
    (project_dir / "agent.py").write_text(example_agent)
    
    # Create README
    readme = f'''# {project_name}

Isolated Agents SDK project.

## Getting Started

1. Install dependencies:
   ```bash
   pip install isolated-agents-sdk
   ```

2. Run the example agent:
   ```bash
   python agent.py
   ```

3. Or use the CLI:
   ```bash
   isolated-agents run example_agent
   ```

## Configuration

Edit `isolated-agents.yaml` to configure your agents.

## Documentation

- [Isolated Agents SDK Documentation](https://github.com/Tech-Vexy/Isolated-Agents)
- [Examples](https://github.com/Tech-Vexy/Isolated-Agents/tree/main/examples)
'''
    
    (project_dir / "README.md").write_text(readme)
    
    print(f"✓ Created project: {project_name}")
    print(f"\nNext steps:")
    print(f"  cd {project_name}")
    print(f"  python agent.py")
    
    return 0


def cmd_config_create(args):
    """Create default configuration file."""
    from isolated_agents_sdk.config import create_default_config
    
    config_path = Path(args.output or "isolated-agents.yaml")
    
    if config_path.exists() and not args.force:
        print(f"Error: Configuration file already exists: {config_path}", file=sys.stderr)
        print(f"Use --force to overwrite", file=sys.stderr)
        return 1
    
    create_default_config(config_path)
    print(f"✓ Created configuration: {config_path}")
    
    return 0


def cmd_config_list(args):
    """List agents in configuration."""
    from isolated_agents_sdk.config import load_config
    
    config_path = Path(args.config or "isolated-agents.yaml")
    
    if not config_path.exists():
        print(f"Error: Configuration file not found: {config_path}", file=sys.stderr)
        return 1
    
    config = load_config(config_path)
    agents = config.list_agents()
    
    if not agents:
        print("No agents configured")
        return 0
    
    print(f"Agents in {config_path}:")
    for name in agents:
        agent_config = config.get_agent(name)
        print(f"  • {name}")
        if agent_config.description:
            print(f"    {agent_config.description}")
        print(f"    Workspace: {agent_config.workspace}")
        if agent_config.output:
            print(f"    Output: {agent_config.output}")
    
    return 0


def cmd_run(args):
    """Run an agent from configuration."""
    from isolated_agents_sdk.config import load_config
    
    config_path = Path(args.config or "isolated-agents.yaml")
    
    if not config_path.exists():
        print(f"Error: Configuration file not found: {config_path}", file=sys.stderr)
        print(f"Create one with: isolated-agents config create", file=sys.stderr)
        return 1
    
    # Load config
    config = load_config(config_path)
    
    # Get agent config
    try:
        agent_config = config.get_agent(args.agent)
    except KeyError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    
    # Load agent function
    agent_file = Path(args.file or "agent.py")
    if not agent_file.exists():
        print(f"Error: Agent file not found: {agent_file}", file=sys.stderr)
        return 1
    
    # Import agent function
    import importlib.util
    spec = importlib.util.spec_from_file_location("agent_module", agent_file)
    if not spec or not spec.loader:
        print(f"Error: Could not load agent file: {agent_file}", file=sys.stderr)
        return 1
    
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    
    # Get agent function
    func_name = args.function or args.agent
    if not hasattr(module, func_name):
        print(f"Error: Function '{func_name}' not found in {agent_file}", file=sys.stderr)
        return 1
    
    agent_func = getattr(module, func_name)
    
    # Create and run agent
    from isolated_agents_sdk import Agent
    
    agent = Agent.from_config(config, args.agent, agent_func)
    
    print(f"Running agent: {args.agent}")
    print(f"Workspace: {agent._workspace}")
    if agent._output:
        print(f"Output: {agent._output}")
    print()
    
    result = agent.run()
    
    print()
    print(f"✓ Agent completed with exit code: {result.exit_code}")
    
    if result.artifacts:
        print(f"\nArtifacts:")
        for name, path in result.artifacts.items():
            print(f"  • {name}: {path}")
    
    return result.exit_code


def cmd_ps(args):
    """List running agents."""
    from isolated_agents_sdk import list_sessions
    
    sessions = list_sessions()
    
    if not sessions:
        print("No running agents")
        return 0
    
    print(f"Running agents ({len(sessions)}):")
    print()
    
    for session in sessions:
        print(f"Session: {session.session_id}")
        print(f"  Agent: {session.agent_id}")
        print(f"  Container: {session.container_id[:12]}")
        print(f"  Started: {session.started_at}")
        print(f"  Status: {session.status}")
        if session.error:
            print(f"  Error: {session.error}")
        print()
    
    return 0


def cmd_logs(args):
    """View agent logs."""
    print(f"Viewing logs for session: {args.session_id}")
    print("(Log viewing not yet implemented)")
    return 0


def cmd_stop(args):
    """Stop a running agent."""
    print(f"Stopping session: {args.session_id}")
    print("(Stop command not yet implemented)")
    return 0


def cmd_cleanup(args):
    """Clean up resources."""
    print("Cleaning up resources...")
    
    # Stop all running agents
    from isolated_agents_sdk import list_sessions
    
    sessions = list_sessions()
    
    if not sessions:
        print("No running agents to clean up")
        return 0
    
    print(f"Found {len(sessions)} running agents")
    
    if not args.force:
        response = input("Stop all agents? [y/N]: ")
        if response.lower() != 'y':
            print("Cancelled")
            return 0
    
    print("(Cleanup not yet fully implemented)")
    
    return 0


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="isolated-agents",
        description="Isolated Agents SDK command-line tool",
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # init command
    init_parser = subparsers.add_parser("init", help="Initialize new project")
    init_parser.add_argument("name", help="Project name")
    
    # config commands
    config_parser = subparsers.add_parser("config", help="Manage configuration")
    config_subparsers = config_parser.add_subparsers(dest="config_command")
    
    config_create = config_subparsers.add_parser("create", help="Create default config")
    config_create.add_argument("-o", "--output", help="Output file path")
    config_create.add_argument("-f", "--force", action="store_true", help="Overwrite existing")
    
    config_list = config_subparsers.add_parser("list", help="List agents in config")
    config_list.add_argument("-c", "--config", help="Config file path")
    
    # run command
    run_parser = subparsers.add_parser("run", help="Run agent from config")
    run_parser.add_argument("agent", help="Agent name from config")
    run_parser.add_argument("-c", "--config", help="Config file path")
    run_parser.add_argument("-f", "--file", help="Agent file path")
    run_parser.add_argument("--function", help="Function name (defaults to agent name)")
    
    # ps command
    ps_parser = subparsers.add_parser("ps", help="List running agents")
    
    # logs command
    logs_parser = subparsers.add_parser("logs", help="View agent logs")
    logs_parser.add_argument("session_id", help="Session ID")
    
    # stop command
    stop_parser = subparsers.add_parser("stop", help="Stop running agent")
    stop_parser.add_argument("session_id", help="Session ID")
    
    # cleanup command
    cleanup_parser = subparsers.add_parser("cleanup", help="Clean up resources")
    cleanup_parser.add_argument("-f", "--force", action="store_true", help="Don't ask for confirmation")
    
    # Parse arguments
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    # Route to command handler
    try:
        if args.command == "init":
            return cmd_init(args)
        elif args.command == "config":
            if args.config_command == "create":
                return cmd_config_create(args)
            elif args.config_command == "list":
                return cmd_config_list(args)
            else:
                config_parser.print_help()
                return 1
        elif args.command == "run":
            return cmd_run(args)
        elif args.command == "ps":
            return cmd_ps(args)
        elif args.command == "logs":
            return cmd_logs(args)
        elif args.command == "stop":
            return cmd_stop(args)
        elif args.command == "cleanup":
            return cmd_cleanup(args)
        else:
            parser.print_help()
            return 1
    except KeyboardInterrupt:
        print("\nInterrupted")
        return 130
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback
        if "--debug" in sys.argv:
            traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
