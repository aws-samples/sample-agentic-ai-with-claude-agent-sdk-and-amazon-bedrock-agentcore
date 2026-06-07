"""FAST — the heart of Module 2: the deploy path REUSES Module 1's agent, no fork.

If these pass, agent identity has one source of truth and the old track's
"5 copy-pasted agent files" trap is avoided.
"""
from __future__ import annotations

import inspect
import sys

from conftest import AGENT_DIR, MODULE1_AGENT

sys.path.insert(0, str(AGENT_DIR))


def test_entrypoint_imports_shared_options():
    """agent_agentcore.py imports build_agent_options from agent.py."""
    import agent_agentcore

    src = inspect.getsource(agent_agentcore)
    assert "from agent import" in src
    assert "build_agent_options" in src


def test_entrypoint_has_no_duplicated_agent_logic():
    """The thin wrapper must NOT redefine the agent's identity."""
    import agent_agentcore

    src = inspect.getsource(agent_agentcore)
    assert "system_prompt=" not in src, "entrypoint should not set system_prompt"
    assert "create_sdk_mcp_server" not in src, "entrypoint should not redefine the MCP server"
    assert "allowed_tools=" not in src, "entrypoint should not hardcode the tool list"


def test_entrypoint_exposes_agentcore_app():
    import agent_agentcore

    app = agent_agentcore.app
    assert type(app).__name__ == "BedrockAgentCoreApp"


def test_agent_py_identical_to_module1():
    """The copied bundle must not drift from Module 1's source of truth."""
    assert (AGENT_DIR / "agent.py").read_text() == MODULE1_AGENT.read_text(), (
        "module-2 agent.py has drifted from module-1 agent.py — re-sync the bundle"
    )


def test_no_observable_agent_files():
    """The old hand-rolled *_observable.py family must NOT reappear."""
    offenders = list(AGENT_DIR.glob("*observable*"))
    assert not offenders, f"hand-rolled observability files found: {offenders}"
