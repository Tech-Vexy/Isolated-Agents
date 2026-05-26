"""
Example demonstrating Secure Database Access (v0.2.1 Hardening).

Features:
- SQL Injection Guard: The Host Runtime validates raw SQL queries before execution.
- Mediated Access: Agents never see DB credentials; they communicate via logic IDs.
- Parameterized Queries: demonstrating safe interaction.
"""

from isolated_agents_sdk import run_agent, Policy
from isolated_agents_sdk.sub_agent_client import db_query, db_execute, db_set, db_get
import os

def my_db_agent():
    """An agent that interacts with mediated databases."""
    print("Running database agent...")

    # 1. SQL Interaction (v0.2.1 Hardening applies here)
    print("Direct mediated SQL interaction...")
    db_execute("main_sql", "CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, name TEXT)")

    # Using parameters (Recommended)
    db_execute("main_sql", "INSERT INTO users (name) VALUES (?)", ("Alice",))

    rows = db_query("main_sql", "SELECT * FROM users")
    print(f"SQL Rows (Retrieved via host IPC): {rows}")

    # Demonstration of SQL Injection Defense (this would raise an exception on the host side)
    # try:
    #     db_execute("main_sql", "SELECT * FROM users; DROP TABLE users")
    # except Exception as e:
    #     print(f"Host blocked unsafe query: {e}")

    # 2. NoSQL Interaction
    print("Setting value in NoSQL...")
    db_set("main_nosql", "app_config", {"theme": "dark", "version": "0.2.1"}, collection="settings")

    config = db_get("main_nosql", "app_config", collection="settings")
    print(f"NoSQL Config: {config}")

    return f"Completed DB tasks. Processed {len(rows)} SQL records."

if __name__ == "__main__":
    # Configure the host-side adapters (Simulated Production Environment)
    from isolated_agents_sdk import configure_adapters

    configure_adapters(config={
        "database_adapters": {
            "main_sql": {
                "type": "sql",
                "url": "sqlite:///./test_db.sqlite"
            },
            "main_nosql": {
                "type": "nosql",
                "provider": "memory"
            }
        }
    })

    # Define the policy (RBAC: db_id mapping)
    my_policy = Policy(
        database_access={
            "main_sql": {"type": "sql"},
            "main_nosql": {"type": "nosql"}
        }
    )

    print("--- Launching Database Mediated Agent ---")
    result = run_agent(my_db_agent, working_dir="./db_agent_workspace", policy=my_policy)

    if result.exit_code == 0:
        print(f"Agent result: {result.output}")
    else:
        print(f"Agent failed: {result.error}")
