#!/usr/bin/env python3
"""
Main entry point for AgentCore deployment - Follow-up Agent with Clarification Support.
Module 4: Implements multi-round clarification using AskUserQuestion tool.
"""

from importlib import import_module

# Import the app from the module-4 follow-up agent
followup_module = import_module("module-4-improve-agentic-workflow.followup_agent_agentcore")
app = followup_module.app

# Re-export app for AgentCore
__all__ = ['app']

if __name__ == "__main__":
    # Run the AgentCore app
    app.run()
