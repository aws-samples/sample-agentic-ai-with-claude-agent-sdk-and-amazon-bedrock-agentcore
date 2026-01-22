#!/usr/bin/env python3
"""
Main entry point for AgentCore deployment WITH OBSERVABILITY.
Imports the app from agent/agent_agentcore_observable.py which includes
OpenTelemetry custom spans for agent workflow tracking.

For Module 3b: AgentCore Deployment with Observability
"""

from agent.agent_agentcore_observable import app

# Re-export app for AgentCore
__all__ = ['app']

if __name__ == "__main__":
    # Run the AgentCore app with observability
    app.run()
