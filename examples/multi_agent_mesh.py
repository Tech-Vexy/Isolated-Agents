"""
Example demonstrating a Collaborative Multi-Agent Mesh using v0.2.0 Ingress.
Agents run as network-reachable nodes that can exchange data via TCP/HTTP 
while remaining in their own isolated sandboxes.
"""

import asyncio
import logging
import requests
import json
from isolated_agents_sdk import AgentRuntime, Policy, NetworkPolicy
from isolated_agents_sdk.logging import setup_logging

# --- Agent Node Logic ---
def agent_node(port: int, peer_port: int = None):
    from http.server import HTTPServer, BaseHTTPRequestHandler
    import threading
    import time

    class NodeHandler(BaseHTTPRequestHandler):
        def do_POST(self):
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            msg = json.loads(post_data)
            print(f"[Node {port}] Received message: {msg['text']}")
            
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'{"status": "received"}')

    # Start the server in a thread
    server = HTTPServer(('0.0.0.0', port), NodeHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    print(f"[Node {port}] Listening for peer messages...")

    # If we have a peer, try to send a "Handshake"
    if peer_port:
        time.sleep(5) # Wait for peer to be up
        try:
            print(f"[Node {port}] Pinging peer at port {peer_port}...")
            # Note: In a bridge network, agents reach each other via the host IP
            # For this demo, we assume they are mapped to localhost on the host.
            resp = requests.post(
                f"http://host.containers.internal:{peer_port}", 
                json={"text": f"Greetings from Agent on {port}!"},
                timeout=5
            )
            print(f"[Node {port}] Peer response: {resp.status_code}")
        except Exception as e:
            print(f"[Node {port}] Could not reach peer: {e}")

    # Keep alive for demonstration
    time.sleep(15)
    server.shutdown()
    return f"Node {port} finished collaboration."

async def main():
    setup_logging(level=logging.INFO)
    runtime = AgentRuntime(working_dir="./mesh_workspace")
    await runtime.start()
    
    try:
        # Launch two agents in parallel that talk to each other
        # Node A: Port 9001 -> Peer 9002
        # Node B: Port 9002 -> Peer 9001
        
        policy_a = Policy(network=NetworkPolicy(disabled=False, ingress_ports=[9001]))
        policy_b = Policy(network=NetworkPolicy(disabled=False, ingress_ports=[9002]))

        print("--- Launching Collaborative Mesh ---")
        
        # We run them concurrently
        results = await asyncio.gather(
            runtime.run_agent(agent_node, policy=policy_a, kwargs={"port": 9001, "peer_port": 9002}),
            runtime.run_agent(agent_node, policy=policy_b, kwargs={"port": 9002, "peer_port": 9001})
        )
        
        for r in results:
            print(r.output)
            
    finally:
        await runtime.stop()

if __name__ == "__main__":
    asyncio.run(main())
吐