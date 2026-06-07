"""FAST — the deployment config is well-formed: agentcore.json, Dockerfile, gitignore hygiene."""
from __future__ import annotations

import json

import pytest

from conftest import AGENT_DIR, AGENTCORE_DIR, MODULE_DIR


def test_agentcore_json_runtime_shape():
    cfg = json.load(open(AGENTCORE_DIR / "agentcore.json"))
    assert len(cfg["runtimes"]) == 1
    rt = cfg["runtimes"][0]
    assert rt["build"] == "Container"            # CodeZip is blocked for this SDK (bundled binary)
    assert rt["protocol"] == "HTTP"
    assert rt["entrypoint"] == "agent_agentcore.py"
    assert rt["codeLocation"].rstrip("/") == "chief_of_staff_agent"
    # OTel groundwork for Module 4
    assert rt.get("instrumentation", {}).get("enableOtel") is True
    # Bedrock env wired for the deployed runtime
    env = {e["name"]: e["value"] for e in rt.get("envVars", [])}
    assert env.get("CLAUDE_CODE_USE_BEDROCK") == "1"
    assert "ANTHROPIC_MODEL" in env


def test_dockerfile_is_arm64_and_installs_deps():
    df = (AGENT_DIR / "Dockerfile").read_text()
    assert "linux/arm64" in df, "AgentCore Runtime requires arm64 images"
    assert "pip install" in df, "must install the SDK fresh (gives the bundled binary correct perms/arch)"
    assert "aws-opentelemetry-distro" in df or "pip install ." in df  # OTel present via pyproject
    assert "agent_agentcore.py" in df, "CMD must run the entrypoint"


def test_container_deps_pinned():
    """The in-container pyproject pins the SDK + agentcore + otel exactly."""
    txt = (AGENT_DIR / "pyproject.toml").read_text()
    assert "claude-agent-sdk==0.2.88" in txt
    assert "bedrock-agentcore==" in txt
    assert "aws-opentelemetry-distro==" in txt


def test_account_id_not_committed():
    """aws-targets.json (real account id) must be gitignored; only the .example is tracked."""
    gi = (AGENTCORE_DIR / ".gitignore").read_text()
    assert "aws-targets.json" in gi
    assert (AGENTCORE_DIR / "aws-targets.example.json").exists()


def test_env_example_present_and_bedrock():
    env = (MODULE_DIR / ".env.example").read_text()
    assert "CLAUDE_CODE_USE_BEDROCK" in env and "ANTHROPIC_MODEL" in env
