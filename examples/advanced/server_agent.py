"""Example of a server-based agent (Flask web server)."""

import time
from isolated_agents_sdk import run_agent, Policy, NetworkPolicy

def web_server_agent():
    """Agent that runs a simple Flask web server."""
    from flask import Flask
    
    app = Flask(__name__)
    
    @app.route("/")
    def hello():
        return {"message": "Hello from the isolated sandbox!"}
    
    print("Starting Flask server on port 5000...")
    # Run server in a way that it lives for a bit
    app.run(host="0.0.0.0", port=5000)

if __name__ == "__main__":
    # Configure policy to allow ingress on port 5000
    policy = Policy(
        network=NetworkPolicy(
            disabled=False,
            ingress_ports=[5000]
        ),
        pip_packages=["flask"],
        # Give it a longer timeout as servers usually run for a while
        timeout_seconds=300
    )
    
    print("Launching server-based agent...")
    print("Once started, you can access it at http://localhost:5000 (if running locally with Podman/Docker)")
    
    # In a real scenario, this would likely be run with interactive=True 
    # or as a long-running background task.
    result = run_agent(
        web_server_agent, 
        working_dir="./server_agent_workspace",
        policy=policy
    )
    
    print(f"Agent finished with exit code: {result.exit_code}")
