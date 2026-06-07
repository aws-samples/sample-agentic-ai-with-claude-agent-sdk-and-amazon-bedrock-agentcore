"""FAST — the heart of Module 2: prove the deploy path REUSES Module 1's agent, no duplication.

If these pass, we have one source of truth for agent identity and the "two copies" trap is avoided.
"""
from __future__ import annotations

import ast
import inspect
import sys

import pytest

from conftest import AGENT_DIR, MODULE1_AGENT

sys.path.insert(0, str(AGENT_DIR))


def test_entrypoint_imports_shared_options():
    """agent_agentcore.py imports build_agent_options from agent.py (the shared identity)."""
    import agent_agentcore

    src = inspect.getsource(agent_agentcore)
    assert "from agent import build_agent_options" in src
    assert "build_agent_options(" in src


def test_entrypoint_has_no_duplicated_agent_logic():
    """The thin wrapper must NOT redefine the agent's identity (system prompt / tool list).

    Guards against drift back toward the archived ~360-line duplicate.
    """
    import agent_agentcore

    src = inspect.getsource(agent_agentcore)
    # No inline system prompt and no hardcoded Chief-of-Staff persona in the entrypoint.
    assert "system_prompt=" not in src, "entrypoint should not set system_prompt — that lives in build_agent_options"
    assert "Chief of Staff for TechStart" not in src, "entrypoint duplicates the system prompt"
    # No hardcoded allowed_tools list in the entrypoint.
    assert "allowed_tools=" not in src


def test_entrypoint_exposes_agentcore_app():
    """The module exposes a BedrockAgentCoreApp with the runtime HTTP contract."""
    import agent_agentcore

    app = agent_agentcore.app
    assert type(app).__name__ == "BedrockAgentCoreApp"
    paths = {getattr(r, "path", "") for r in app.router.routes} if hasattr(app, "router") else set()
    assert "/invocations" in paths and "/ping" in paths


def test_build_agent_options_override_hooks():
    """build_agent_options supports the override hooks Modules 3/4 rely on."""
    from agent import build_agent_options

    base = build_agent_options()
    assert base.allowed_tools and base.setting_sources == ["project"]

    extended = build_agent_options(extra_tools=["mcp__memory__store"], max_turns=99)
    assert "mcp__memory__store" in extended.allowed_tools
    assert extended.max_turns == 99
    # base is unaffected by the override (no shared-state leakage)
    assert "mcp__memory__store" not in base.allowed_tools


def test_no_hardcoded_model_anywhere():
    """Bedrock: model comes from env, never hardcoded (in either agent file)."""
    for f in (AGENT_DIR / "agent.py", AGENT_DIR / "agent_agentcore.py"):
        assert "claude-opus-4-6" not in f.read_text()


def test_agent_py_identical_to_module1():
    """The copied agent bundle must not drift from Module 1's source of truth."""
    assert (AGENT_DIR / "agent.py").read_text() == MODULE1_AGENT.read_text(), (
        "module-2 agent.py has drifted from module-1 agent.py — re-sync the bundle"
    )
