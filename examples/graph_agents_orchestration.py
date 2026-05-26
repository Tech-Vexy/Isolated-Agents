"""
Example demonstrating Graph-based Multi-Agent Orchestration (v0.2.0).
Uses StateGraph to manage nodes, edges, and conditional transitions.
"""

import asyncio
from isolated_agents_sdk import (
    isolated_agent,
    StateGraph,
    setup_logging,
    Policy,
    NetworkPolicy
)

# 1. Define Isolated Agents as nodes
@isolated_agent
def researcher(state: dict):
    print(f"[Node: Researcher] Researching topic: {state.get('topic')}")
    # In a real agent, this would use LLMs/Search
    return {"research": f"Detailed facts about {state.get('topic')}"}

@isolated_agent
def writer(state: dict):
    print(f"[Node: Writer] Writing article based on: {state.get('research')}")
    return {"article": f"An amazing article about {state.get('topic')} using {state.get('research')}"}

@isolated_agent
def quality_checker(state: dict):
    article = state.get("article", "")
    print(f"[Node: Quality Checker] Checking article length: {len(article)}")

    # Simple logic: if article is too short, mark for revision
    is_good = len(article) > 50
    return {"is_approved": is_good, "revision_needed": not is_good}

# 2. Define Routing Logic
def router(state: dict):
    if state.get("is_approved"):
        return "approved"
    else:
        return "revise"

async def main():
    setup_logging()

    # 3. Build the StateGraph
    workflow = StateGraph()

    # Add Nodes
    workflow.add_node("research", researcher)
    workflow.add_node("write", writer)
    workflow.add_node("check", quality_checker)

    # Define Edges (Transitions)
    workflow.add_edge("research", "write")
    workflow.add_edge("write", "check")

    # Define Conditional Edge (Routing)
    workflow.add_conditional_edges(
        "check",
        router,
        {
            "approved": "__END__",
            "revise": "write"  # Loop back if not approved
        }
    )

    workflow.set_entry_point("research")

    # 4. Compile and Run
    print("--- Starting Graph Agent Orchestration ---")
    app = workflow.compile()

    final_state = await app(initial_state={"topic": "Graph-based Agents"})

    print("\n--- Final Workflow State ---")
    print(f"Topic: {final_state.get('topic')}")
    print(f"Approved: {final_state.get('is_approved')}")
    print(f"Article: {final_state.get('article')}")

if __name__ == "__main__":
    asyncio.run(main())

