"""File Summariser — LangChain + Groq agent wrapped in the Isolated Agents SDK.

The agent reads every text file in its working directory (/workspace inside the
container) and writes a Markdown summary to /output/summary.md.

Usage
-----
    # Set your Groq API key first:
    export GROQ_API_KEY=gsk_...

    uv run python examples/file_summariser.py [path/to/workdir]

If no path is given the current directory is used.
The summary is printed to stdout and also saved to ./output/summary.md.
"""

import os
import sys
from pathlib import Path

# NOTE: `from __future__ import annotations` must NOT be used at module level
# when the module contains functions serialised with cloudpickle. cloudpickle
# reconstructs bytecode in the container where the future import is absent,
# causing UnboundLocalError on locals that Python compiled as annotated.


# ---------------------------------------------------------------------------
# The agent callable — this function is serialised with cloudpickle and run
# *inside* the container, so it must be self-contained (all imports inside).
# ---------------------------------------------------------------------------

def summarise_files() -> None:
    """Read every .txt / .md file in /workspace and write a summary to /output."""
    import os
    import pathlib
    from langchain_groq import ChatGroq
    from langchain_core.messages import HumanMessage, SystemMessage

    workspace = pathlib.Path("/workspace")
    output_dir = pathlib.Path("/output")
    output_dir.mkdir(parents=True, exist_ok=True)

    # Collect text files
    files = sorted(
        fp for fp in workspace.rglob("*")
        if fp.is_file() and fp.suffix in (".txt", ".md", ".py", ".json", ".yaml", ".yml")
    )

    if not files:
        (output_dir / "summary.md").write_text("No text files found in working directory.\n")
        return

    # Build a single prompt with all file contents (truncated to keep tokens sane)
    MAX_CHARS_PER_FILE = 2000
    file_sections = []
    for fp in files:
        try:
            content = fp.read_text(errors="replace")[:MAX_CHARS_PER_FILE]
        except Exception as exc:
            content = f"<error reading file: {exc}>"
        rel = fp.relative_to(workspace)
        file_sections.append(f"### {rel}\n```\n{content}\n```")

    combined = "\n\n".join(file_sections)

    llm = ChatGroq(
        model="llama-3.3-70b-versatile",
        api_key=os.environ["GROQ_API_KEY"],
    )

    messages = [
        SystemMessage(content=(
            "You are a helpful assistant. "
            "Summarise the provided files concisely in Markdown. "
            "Include a one-sentence description of each file."
        )),
        HumanMessage(content=f"Please summarise these files:\n\n{combined}"),
    ]

    response = llm.invoke(messages)
    summary = response.content

    (output_dir / "summary.md").write_text(summary + "\n")
    print(summary)


# ---------------------------------------------------------------------------
# Entry point — wraps the agent in the SDK and runs it
# ---------------------------------------------------------------------------

def main() -> None:
    from dotenv import load_dotenv
    load_dotenv()

    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        print("Error: GROQ_API_KEY environment variable is not set.", file=sys.stderr)
        sys.exit(1)

    workdir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.cwd()
    if not workdir.exists():
        print(f"Error: working directory '{workdir}' does not exist.", file=sys.stderr)
        sys.exit(1)

    host_output = Path("output")
    host_output.mkdir(exist_ok=True)

    # Build a policy that forwards the API key into the container
    # and allows outbound network access (needed to reach the Groq API).
    from isolated_agents_sdk import Policy, NetworkPolicy, run_agent

    policy = Policy(
        network=NetworkPolicy(disabled=False),
        allowed_env_vars=["GROQ_API_KEY"],
        pip_packages=["langchain-groq", "langchain-core"],
        output_path_in_container="/output",
    )

    print(f"Launching isolated agent on: {workdir}")
    result = run_agent(
        agent=summarise_files,
        working_dir=workdir,
        policy=policy,
        host_output_path=host_output,
    )

    print(f"\nAgent exited with code {result.exit_code}")
    if result.artifacts:
        print(f"Output written to: {host_output}/")
        for name in result.artifacts:
            print(f"  {name} ({len(result.artifacts[name])} bytes)")
    else:
        print("No output artifacts collected.")

    sys.exit(result.exit_code)


if __name__ == "__main__":
    main()
