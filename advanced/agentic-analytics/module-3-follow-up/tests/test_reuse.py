"""FAST — Module 3 adds clarification as an OVERRIDE on the shared agent, no fork."""
from __future__ import annotations

import inspect
import sys

from conftest import AGENT_DIR, MODULE1_AGENT

sys.path.insert(0, str(AGENT_DIR))


def test_agent_py_identical_to_module1():
    """Clarification is a flag on build_agent_options — agent.py must NOT have forked."""
    assert (AGENT_DIR / "agent.py").read_text() == MODULE1_AGENT.read_text(), (
        "module-3 agent.py has drifted from module-1 — clarification is an override, not a fork"
    )


def test_entrypoint_enables_clarification_via_builder():
    """The entrypoint turns on clarification through the shared builder, not a new agent."""
    import agent_agentcore

    src = inspect.getsource(agent_agentcore)
    assert "from agent import" in src and "build_agent_options" in src
    assert "enable_clarification=True" in src
    # no duplicated agent identity
    assert "system_prompt=" not in src
    assert "create_sdk_mcp_server" not in src


def test_entrypoint_supports_session_resume():
    """Multi-round clarification needs SDK session resume."""
    import agent_agentcore

    src = inspect.getsource(agent_agentcore)
    assert "claude_agent_sdk_session_id" in src
    assert "resume" in src


def test_entrypoint_emits_clarification_json():
    """When AskUserQuestion fires, the entrypoint emits a structured block + returns."""
    import agent_agentcore

    src = inspect.getsource(agent_agentcore)
    assert "AskUserQuestion" in src
    assert "clarification_needed" in src


def test_no_observable_agent_files():
    assert not list(AGENT_DIR.glob("*observable*"))
