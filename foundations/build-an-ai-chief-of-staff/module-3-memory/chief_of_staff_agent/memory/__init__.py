"""AgentCore Memory integration for the Chief of Staff agent (Module 3).

The agent's identity still lives in ``agent.py`` (the single source of truth).
This package is the thin memory layer the deploy entrypoint uses to give the
agent cross-session recall — it never redefines the agent.
"""

from .session import get_memory

__all__ = ["get_memory"]
