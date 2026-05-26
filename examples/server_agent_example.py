"""
Example demonstrating a stateful server-based agent using the new v0.2.0 Ingress feature.
This agent runs as a simple HTTP server inside the container, accessible from the host.
"""

import asyncio
import logging
from isolated_agents_sdk import run_agent, Policy, NetworkPolicy
from isolated_agents_sdk.logging import setup_logging

def fast_api_style_server():
    """Simple HTTP server logic to run inside isolation."""
    from http.server import HTTPServer, BaseHTTPRequestHandler
    import json

    class RequestHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            response = {"status": "online", "message": "Hello from the isolated server!"}
            self.wfile.write(json.dumps(response).encode())

    print("Server starting on port 8080...")
    server = HTTPServer(('0.0.0.0', 8080), RequestHandler)
    server.serve_forever()

def main():
    setup_logging(level=logging.INFO)

    # Define policy with Ingress support (Port Mapping)
    # We map container port 8080 to host port 8080
    policy = Policy(
        network=NetworkPolicy(
            disabled=False,
            ingress_ports=[8080]
        ),
        memory_mb=256
    )

    print("--- Launching Isolated Server Agent ---")
    print("This agent will run a web server inside a container.")
    print("You will be able to reach it at http://localhost:8080 while it's running.")

    try:
        # Note: This will block as the server logic is 'serve_forever'
        run_agent(
            agent=fast_api_style_server,
            policy=policy,
            working_dir="./server_workspace"
        )
    except KeyboardInterrupt:
        print("\nShutting down server...")

if __name__ == "__main__":
    main()
