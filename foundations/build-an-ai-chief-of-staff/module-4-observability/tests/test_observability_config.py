"""FAST — Module 4 reuses Module 2's agent unchanged and is wired for observability.

The whole point of Module 4 is that observability needs NO agent-code change: the runtime
auto-instruments, given enableOtel + ADOT (already present from Module 2). These checks lock that in.
"""
from __future__ import annotations

import json
import sys

import pytest

from conftest import AGENT_DIR, AGENTCORE_DIR, MODULE1_AGENT, MODULE_DIR, SCRIPTS_DIR

sys.path.insert(0, str(AGENT_DIR))
sys.path.insert(0, str(SCRIPTS_DIR))


# ──────────────────────────── reuse / no drift
def test_agent_py_identical_to_module1():
    """Observability adds no agent code — agent.py must match Module 1's source of truth."""
    assert (AGENT_DIR / "agent.py").read_text() == MODULE1_AGENT.read_text(), (
        "module-4 agent.py drifted from module-1 — re-sync the bundle"
    )


def test_entrypoint_unchanged_and_thin():
    """The entrypoint is the same thin wrapper (reuses build_agent_options, no manual spans)."""
    src = (AGENT_DIR / "agent_agentcore.py").read_text()
    assert "from agent import build_agent_options" in src
    assert "build_agent_options(" in src
    # No hand-built observability — the runtime auto-instruments. Guard against re-introducing it.
    assert "start_as_current_span" not in src, "Module 4 must NOT hand-build spans — runtime auto-instruments"
    assert "BedrockInstrumentor" not in src
    assert "system_prompt=" not in src  # identity stays in build_agent_options


# ──────────────────────────── observability wiring
def test_agentcore_json_enables_otel():
    rt = json.load(open(AGENTCORE_DIR / "agentcore.json"))["runtimes"][0]
    assert rt.get("instrumentation", {}).get("enableOtel") is True, "enableOtel must be on for auto-instrumentation"
    assert rt["build"] == "Container"
    assert rt["protocol"] == "HTTP"


def test_container_has_adot():
    """ADOT (aws-opentelemetry-distro) must be in the in-container deps — it's what the runtime uses."""
    txt = (AGENT_DIR / "pyproject.toml").read_text()
    assert "aws-opentelemetry-distro==" in txt


def test_dockerfile_arm64():
    df = (AGENT_DIR / "Dockerfile").read_text()
    assert "linux/arm64" in df
    assert "agent_agentcore.py" in df


def test_dockerfile_wraps_with_opentelemetry_instrument():
    """The CMD must wrap the entrypoint with `opentelemetry-instrument` so ADOT actually
    instruments a BYO container (the runtime does NOT auto-inject it for a custom CMD).

    Regression guard for the Module-4 bug where `CMD python agent_agentcore.py` ran the
    agent un-instrumented and no spans reached /aws/spans."""
    df = (AGENT_DIR / "Dockerfile").read_text()
    assert "opentelemetry-instrument" in df, (
        "Dockerfile CMD must launch via `opentelemetry-instrument` — otherwise no traces are exported"
    )
    # and the ADOT pipeline env must be activated
    assert "AGENT_OBSERVABILITY_ENABLED=true" in df


# ──────────────────────────── Transaction Search helper
def test_enable_transaction_search_importable_and_idempotent_shape():
    """The helper imports and exposes an idempotent enable function (no AWS calls here)."""
    import enable_transaction_search as ets

    assert callable(ets.enable_transaction_search)
    # idempotency markers present in the source (checks state before mutating)
    src = (SCRIPTS_DIR / "enable_transaction_search.py").read_text()
    assert "get_trace_segment_destination" in src
    assert "describe_resource_policies" in src  # checks before creating the policy


# ──────────────────────────── hygiene
def test_account_id_not_committed():
    gi = (AGENTCORE_DIR / ".gitignore").read_text()
    assert "aws-targets.json" in gi
    assert (AGENTCORE_DIR / "aws-targets.example.json").exists()


def test_env_example_bedrock():
    env = (MODULE_DIR / ".env.example").read_text()
    assert "CLAUDE_CODE_USE_BEDROCK" in env and "ANTHROPIC_MODEL" in env
