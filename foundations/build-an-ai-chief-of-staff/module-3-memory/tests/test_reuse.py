"""FAST — Module 3 keeps Module 1's agent as the single source of truth.

Memory is layered ON TOP via the entrypoint + the additive `system_prompt_suffix`
seam — it must NOT fork the agent. These guards prove the deploy path still reuses
`build_agent_options()` with no duplicated identity, exactly like Module 2.
"""
from __future__ import annotations

import inspect
import sys

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

    Memory is injected via `system_prompt_suffix=` (assembled inside build_agent_options),
    so the literal `system_prompt=` must still be absent from the entrypoint.
    """
    import agent_agentcore

    src = inspect.getsource(agent_agentcore)
    assert "system_prompt=" not in src, "entrypoint should not set system_prompt — that lives in build_agent_options"
    assert "system_prompt_suffix=" in src, "memory is injected via the additive suffix seam"
    assert "Chief of Staff for TechStart" not in src, "entrypoint duplicates the system prompt"
    assert "allowed_tools=" not in src


def test_entrypoint_takes_context_param():
    """Module 3's entrypoint adds a 2nd param named `context` so the runtime delivers the
    session id. AgentCore only passes context when the param is literally named `context`."""
    import agent_agentcore

    params = list(inspect.signature(agent_agentcore.invoke).parameters)
    assert params[:2] == ["payload", "context"], (
        f"entrypoint must be invoke(payload, context); got {params}"
    )


def test_entrypoint_exposes_agentcore_app():
    """The module exposes a BedrockAgentCoreApp with the runtime HTTP contract."""
    import agent_agentcore

    app = agent_agentcore.app
    assert type(app).__name__ == "BedrockAgentCoreApp"
    paths = {getattr(r, "path", "") for r in app.router.routes} if hasattr(app, "router") else set()
    assert "/invocations" in paths and "/ping" in paths


def test_build_agent_options_suffix_appends():
    """build_agent_options appends system_prompt_suffix to the canonical prompt, without
    mutating the base prompt — this is the seam Module 3 injects recalled memory through."""
    from agent import SYSTEM_PROMPT, build_agent_options

    base = build_agent_options()
    assert base.system_prompt == SYSTEM_PROMPT

    suffixed = build_agent_options(system_prompt_suffix="\n\n## Memory\n- recalled fact")
    assert suffixed.system_prompt.startswith(SYSTEM_PROMPT)
    assert "recalled fact" in suffixed.system_prompt
    # base is unaffected (no shared-state leakage)
    assert base.system_prompt == SYSTEM_PROMPT


def test_build_agent_options_override_hooks():
    """build_agent_options still supports the override hooks (extra_tools / **overrides)."""
    from agent import build_agent_options

    base = build_agent_options()
    assert base.allowed_tools and base.setting_sources == ["project"]

    extended = build_agent_options(extra_tools=["mcp__memory__store"], max_turns=99)
    assert "mcp__memory__store" in extended.allowed_tools
    assert extended.max_turns == 99
    assert "mcp__memory__store" not in base.allowed_tools


def test_no_hardcoded_model_anywhere():
    """Bedrock: model comes from env, never hardcoded (in either agent file)."""
    for f in (AGENT_DIR / "agent.py", AGENT_DIR / "agent_agentcore.py"):
        assert "claude-opus-4-6" not in f.read_text()


def test_agent_py_identical_to_module1():
    """The copied agent bundle must not drift from Module 1's source of truth."""
    assert (AGENT_DIR / "agent.py").read_text() == MODULE1_AGENT.read_text(), (
        "module-3 agent.py has drifted from module-1 agent.py — re-sync the bundle"
    )
