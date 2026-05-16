import sys
from pathlib import Path
from dotenv import load_dotenv
from isolated_agents_sdk import run_agent, Policy, NetworkPolicy

# Load environment variables from .env file
load_dotenv()

def langchain_agent():
    """Simple LangChain agent that uses Groq."""
    import os as _os
    import pathlib as _pathlib
    from langchain_core.prompts import ChatPromptTemplate
    
    _api_key = _os.environ.get("GROQ_API_KEY")
    if _api_key:
        from langchain_groq import ChatGroq
        _llm = ChatGroq(model="llama-3.3-70b-versatile", temperature=0.7)
        _model_name = "llama-3.3-70b"
    else:
        from langchain_openai import ChatOpenAI
        _llm = ChatOpenAI(model="gpt-4", temperature=0.7)
        _model_name = "gpt-4"
    
    # Create prompt
    _prompt = ChatPromptTemplate.from_messages([
        ("system", "You are a helpful AI assistant."),
        ("user", "{input}")
    ])
    
    # Create chain
    _chain = _prompt | _llm
    
    # Run chain
    _result = _chain.invoke({"input": "Explain quantum computing in simple terms"})
    
    # Save output to /output directory (mapped to host)
    _out = _pathlib.Path("/output")
    _out.mkdir(parents=True, exist_ok=True)
    
    (_out / "response.txt").write_text(_result.content)
    (_out / "metadata.txt").write_text(
        f"Model: {_model_name}\nLength: {len(_result.content)} characters\n"
    )
    
    print(f"[*] Generated response ({len(_result.content)} characters) using {_model_name}")


if __name__ == "__main__":
    import os
    
    # Check for API key
    use_groq = bool(os.environ.get("GROQ_API_KEY"))
    use_openai = bool(os.environ.get("OPENAI_API_KEY"))
    
    if not (use_groq or use_openai):
        print("Error: Neither GROQ_API_KEY nor OPENAI_API_KEY set", file=sys.stderr)
        sys.exit(1)
    
    provider = "Groq" if use_groq else "OpenAI"
    
    # Create output directory
    host_output = Path("./output")
    host_output.mkdir(exist_ok=True)
    
    print(f"Launching LangChain agent using {provider} in isolated container...")
    
    # Prepare policy configuration
    allowed_endpoints = [
        "pypi.org:443", 
        "files.pythonhosted.org:443"
    ]
    if use_groq:
        allowed_endpoints.append("api.groq.com:443")
    else:
        allowed_endpoints.append("api.openai.com:443")
        
    allowed_env_vars = ["GROQ_API_KEY", "OPENAI_API_KEY"]
    pip_packages = ["langchain==0.3.7", "langchain-groq"] if use_groq else ["langchain==0.3.7", "langchain-openai"]
    
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
                allowed_endpoints=allowed_endpoints
            ),
            allowed_env_vars=allowed_env_vars,
            pip_packages=pip_packages,
        )
    )
    
    print(f"\n[*] Agent completed with exit code {result.exit_code}")
    
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
