"""FAST — the heart of Module 1: agent.py is the single source of truth, built correctly.

No creds, no model calls — just constructs ClaudeAgentOptions and inspects them.
"""
from __future__ import annotations

import sys

from conftest import AGENT_DIR

sys.path.insert(0, str(AGENT_DIR))

import agent  # noqa: E402


def test_base_options_shape():
    opts = agent.build_agent_options(request_id="t1")
    assert opts.setting_sources == ["project"]              # loads CLAUDE.md + skills
    assert opts.cwd == agent.AGENT_DIR
    assert "mcp__athena__execute_athena_query" in opts.allowed_tools
    assert "athena" in opts.mcp_servers
    assert "t1" in opts.system_prompt                       # request id wired into prompt


def test_no_hardcoded_model():
    """Bedrock: the model comes from env, never a hardcoded model id in agent.py."""
    src = (AGENT_DIR / "agent.py").read_text()
    for ident in ("claude-opus", "claude-sonnet", "claude-haiku", "anthropic.claude"):
        assert ident not in src, f"hardcoded model id '{ident}' found in agent.py"


def test_clarification_is_an_override_not_a_fork():
    """Module 3's clarification is a flag on the SAME builder — not a separate agent."""
    base = agent.build_agent_options(request_id="b")
    clar = agent.build_agent_options(request_id="c", enable_clarification=True)
    assert "AskUserQuestion" in clar.allowed_tools
    assert "AskUserQuestion" not in base.allowed_tools       # no leakage into base
    assert "AskUserQuestion" in clar.system_prompt           # clarification prompt only when enabled
    assert "AskUserQuestion" not in base.system_prompt


def test_extra_tools_and_overrides():
    opts = agent.build_agent_options(request_id="x", extra_tools=["mcp__memory__store"], max_turns=99)
    assert "mcp__memory__store" in opts.allowed_tools
    assert opts.max_turns == 99


def test_select_only_validator_present():
    """The SQL validator enforces SELECT-only (security) — kept from the original tools."""
    from tools.sql_validator import SQLValidator

    v = SQLValidator(strict_mode=True)
    ok, _ = v.validate("SELECT COUNT(*) FROM student_enrollment_analytics")
    bad, _ = v.validate("DROP TABLE student_enrollment_analytics")
    assert ok is True
    assert bad is False
