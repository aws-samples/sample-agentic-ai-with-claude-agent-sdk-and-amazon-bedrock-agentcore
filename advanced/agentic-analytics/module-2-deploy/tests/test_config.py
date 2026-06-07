"""FAST — agentcore.json + Dockerfile + CDK pin are configured for deploy + observability."""
from __future__ import annotations

import json

from conftest import AGENT_DIR, AGENTCORE_DIR


def _runtime() -> dict:
    cfg = json.loads((AGENTCORE_DIR / "agentcore.json").read_text())
    assert cfg["runtimes"], "no runtime configured"
    return cfg["runtimes"][0]


def test_runtime_is_container_pointing_at_bundle():
    rt = _runtime()
    assert rt["build"] == "Container"           # NOT CodeZip (SDK bundled CLI needs the right arch/perms)
    assert rt["codeLocation"].rstrip("/") == "analytics_agent"
    assert rt["entrypoint"] == "agent_agentcore.py"
    assert rt["runtimeVersion"] == "PYTHON_3_11"


def test_observability_enabled():
    """Module 2 folds in observability: enableOtel on (the CLI does the rest)."""
    rt = _runtime()
    assert rt.get("instrumentation", {}).get("enableOtel") is True


def test_envvars_use_bedrock_no_hardcoded_athena_bucket():
    rt = _runtime()
    names = {e["name"]: e["value"] for e in rt.get("envVars", [])}
    assert names.get("CLAUDE_CODE_USE_BEDROCK") == "1"
    assert "ANTHROPIC_MODEL" in names
    assert names.get("ATHENA_DATABASE") == "student_analytics"
    # the account-specific output bucket must NOT be baked into committed config
    assert "ATHENA_OUTPUT_LOCATION" not in names


def test_dockerfile_wraps_opentelemetry_instrument():
    df = (AGENT_DIR / "Dockerfile").read_text()
    assert "opentelemetry-instrument" in df          # ADOT wrapper (BYO container owns its CMD)
    assert "agent_agentcore.py" in df
    assert "python:3.11" in df                        # deployed Python is 3.11 (the Dockerfile decides)


def test_cdk_lib_is_pinned_exactly():
    """aws-cdk-lib must be pinned (no floating ^) to avoid the schema-54 synth trap."""
    pkg = json.loads((AGENTCORE_DIR / "cdk" / "package.json").read_text())
    ver = pkg["dependencies"]["aws-cdk-lib"]
    assert not ver.startswith("^") and not ver.startswith("~"), f"aws-cdk-lib must be exact, got {ver}"


def test_container_pyproject_has_observability_dep():
    pyproject = (AGENT_DIR / "pyproject.toml").read_text()
    assert "openinference-instrumentation-claude-agent-sdk" in pyproject
    assert "aws-opentelemetry-distro" in pyproject
