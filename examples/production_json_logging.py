"""
Example demonstrating professional structured JSON logging for agent execution.
This format is ideal for production environments using ELK, Splunk, or Datadog.
"""

import logging
from isolated_agents_sdk import run_agent, Policy, setup_logging

def logging_demo_agent(message):
    import logging
    # This also uses the SDK logging inside the container
    logger = logging.getLogger("agent")
    logger.info(f"Agent processing: {message}")
    logger.warning("Simulated resource warning from inside sandbox")
    return "Log generation complete"

def main():
    # Setup structured JSON logging with custom extra fields
    setup_logging(
        level=logging.DEBUG,
        structured=True
    )
    
    logger = logging.getLogger("host-orchestration")
    
    # Policy with specific log path
    policy = Policy(
        memory_mb=256,
        log_output_path="./production_logs/agent_001.json"
    )

    logger.info("Starting production-grade agent execution", extra={
        "environment": "production",
        "region": "us-west-2",
        "agent_version": "v0.2.0"
    })

    result = run_agent(
        agent=logging_demo_agent,
        policy=policy,
        working_dir="./log_workspace",
        agent_kwargs={"message": "Production Test Run"}
    )

    logger.info("Agent execution finished", extra={
        "exit_code": result.exit_code,
        "session_id": result.session_id
    })

if __name__ == "__main__":
    main()
