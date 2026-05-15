"""Basic LangChain agent with Isolated Agents SDK.

This example demonstrates:
- Simple LangChain integration
- OpenAI API usage
- Output artifact collection
- Network policy configuration

Usage:
    export OPENAI_API_KEY=sk-...
    python examples/frameworks/langchain/basic_agent.py
"""

import os
import sys
from pathlib import Path


def langchain_agent():
    """Simple LangChain agent that uses OpenAI."""
    from langchain_openai import ChatOpenAI
    from langchain.prompts import ChatPromptTemplate
    from pathlib import Path
    
    # Create LLM
    llm = ChatOpenAI(model="gpt-4", temperature=0.7)
    
    # Create prompt
    prompt = ChatPromptTemplate.from_messages([
        ("system", "You are a helpful AI assistant."),
        ("user", "{input}")
    ])
    
    # Create chain
    chain = prompt | llm
    
    # Run chain
    result = chain.invoke({"input": "Explain quantum computing in simple terms"})
    
    # Save output to /output directory (mapped to host)
    output_dir = Path("/output")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    (output_dir / "response.txt").write_text(result.content)
    (output_dir / "metadata.txt").write_text(
        f"Model: gpt-4\nLength: {len(result.content)} characters\n"
    )
    
    print(f"✓ Generated response ({len(result.content)} characters)")


if __name__ == "__main__":
    from isolated_agents_sdk import run_agent, Policy, NetworkPolicy
    
    # Check for API key
    if not os.environ.get("OPENAI_API_KEY"):
        print("Error: OPENAI_API_KEY environment variable not set", file=sys.stderr)
        sys.exit(1)
    
    # Create output directory
    host_output = Path("./output")
    host_output.mkdir(exist_ok=True)
    
    print("Launching LangChain agent in isolated container...")
    
    # Run agent in isolated container
    result = run_agent(
        agent=langchain_agent,
        working_dir="./workspace",
        host_output_path=host_output,
        policy=Policy(
            cpu_cores=2.0,
            memory_mb=1024,
            network=NetworkPolicy(
                disabled=False,
                allowed_endpoints=["api.openai.com:443"]
            ),
            allowed_env_vars=["OPENAI_API_KEY"],
            pip_packages=["langchain", "langchain-openai"],
        )
    )
    
    print(f"\n✓ Agent completed with exit code {result.exit_code}")
    
    if result.artifacts:
        print(f"\nOutput artifacts:")
        for name, path in result.artifacts.items():
            size = Path(path).stat().st_size
            print(f"  • {name} ({size} bytes)")
            
        # Display the response
        response_path = result.artifacts.get("response.txt")
        if response_path:
            print(f"\nResponse:\n{Path(response_path).read_text()}")
    
    sys.exit(result.exit_code)

# Made with Bob
