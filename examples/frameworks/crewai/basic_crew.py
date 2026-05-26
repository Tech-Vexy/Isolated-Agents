"""Basic CrewAI crew with Isolated Agents SDK.

This example demonstrates:
- CrewAI agent and task definition
- Multi-agent collaboration
- Sequential task execution
- Output artifact collection

Usage:
    export OPENAI_API_KEY=sk-...
    python examples/frameworks/crewai/basic_crew.py
"""

import os
import sys
from pathlib import Path


def crewai_agent():
    """CrewAI crew for content creation."""
    from crewai import Agent, Task, Crew
    from langchain_openai import ChatOpenAI
    from pathlib import Path

    llm = ChatOpenAI(model="gpt-4")

    # Define agents
    researcher = Agent(
        role="Researcher",
        goal="Research topics thoroughly and provide accurate information",
        backstory="You are an expert researcher with attention to detail and fact-checking skills.",
        llm=llm,
        verbose=True
    )

    writer = Agent(
        role="Writer",
        goal="Write engaging and informative content",
        backstory="You are a professional content writer who creates clear, compelling articles.",
        llm=llm,
        verbose=True
    )

    editor = Agent(
        role="Editor",
        goal="Review and improve content quality",
        backstory="You are an experienced editor who ensures content is polished and error-free.",
        llm=llm,
        verbose=True
    )

    # Define tasks
    research_task = Task(
        description="Research the latest developments in AI safety and best practices",
        agent=researcher,
        expected_output="A comprehensive research summary with key findings"
    )

    writing_task = Task(
        description="Write an engaging article about AI safety based on the research",
        agent=writer,
        expected_output="A well-structured article of 500-800 words"
    )

    editing_task = Task(
        description="Review and polish the article for clarity and impact",
        agent=editor,
        expected_output="A final, publication-ready article"
    )

    # Create crew
    crew = Crew(
        agents=[researcher, writer, editor],
        tasks=[research_task, writing_task, editing_task],
        verbose=True
    )

    # Run crew
    print("Starting CrewAI crew execution...")
    result = crew.kickoff()

    # Save output
    output_dir = Path("/output")
    output_dir.mkdir(parents=True, exist_ok=True)

    (output_dir / "article.txt").write_text(str(result))
    (output_dir / "metadata.txt").write_text(
        f"Agents: {len(crew.agents)}\n"
        f"Tasks: {len(crew.tasks)}\n"
        f"Output length: {len(str(result))} characters\n"
    )

    print("✓ Crew completed successfully")
    print(f"✓ Generated article ({len(str(result))} characters)")


if __name__ == "__main__":
    from isolated_agents_sdk import run_agent, Policy, NetworkPolicy

    if not os.environ.get("OPENAI_API_KEY"):
        print("Error: OPENAI_API_KEY environment variable not set", file=sys.stderr)
        sys.exit(1)

    host_output = Path("./output")
    host_output.mkdir(exist_ok=True)

    print("Launching CrewAI crew in isolated container...")

    result = run_agent(
        agent=crewai_agent,
        working_dir="./workspace",
        host_output_path=host_output,
        policy=Policy(
            cpu_cores=4.0,
            memory_mb=2048,
            network=NetworkPolicy(disabled=False),
            allowed_env_vars=["OPENAI_API_KEY"],
            pip_packages=["crewai", "langchain-openai"],
            timeout_seconds=600,  # CrewAI can take longer
        )
    )

    print(f"\n✓ Crew completed with exit code {result.exit_code}")

    if result.artifacts:
        print("\nOutput artifacts:")
        for name, path in result.artifacts.items():
            size = Path(path).stat().st_size
            print(f"  • {name} ({size} bytes)")

        article_path = result.artifacts.get("article.txt")
        if article_path:
            print(f"\nArticle:\n{Path(article_path).read_text()}")

    sys.exit(result.exit_code)

# Made with Bob
