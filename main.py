#!/usr/bin/env python3
"""
Main entry point for AgentCore deployment.
Imports the app from agent/agent_agentcore.py
"""

from agent.agent_agentcore import app

# Re-export app for AgentCore
__all__ = ['app']

if __name__ == "__main__":
    # Run the AgentCore app
    app.run()
