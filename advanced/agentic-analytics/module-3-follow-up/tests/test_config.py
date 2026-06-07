"""FAST — agentcore.json + Dockerfile + CDK pin (same deploy guarantees as M2)."""
from __future__ import annotations

import json

from conftest import AGENT_DIR, AGENTCORE_DIR


def _runtime() -> dict:
    cfg = json.loads((AGENTCORE_DIR / "agentcore.json").read_text())
    assert cfg["runtimes"], "no runtime configured"
    return cfg["runtimes"][0]


def test_distinct_project_name_from_module2():
    """M3 must not share M2's stack name (else concurrent deploys collide)."""
    cfg = json.loads((AGENTCORE_DIR / "agentcore.json").read_text())
    assert cfg["name"] != "aaanalytics", "M3 must use a distinct project name"


def test_runtime_container_and_observability():
    rt = _runtime()
    assert rt["build"] == "Container"
    assert rt["entrypoint"] == "agent_agentcore.py"
    assert rt.get("instrumentation", {}).get("enableOtel") is True


def test_dockerfile_wraps_opentelemetry_instrument():
    df = (AGENT_DIR / "Dockerfile").read_text()
    assert "opentelemetry-instrument" in df
    assert "python:3.11" in df


def test_cdk_lib_is_pinned_exactly():
    pkg = json.loads((AGENTCORE_DIR / "cdk" / "package.json").read_text())
    ver = pkg["dependencies"]["aws-cdk-lib"]
    assert not ver.startswith(("^", "~")), f"aws-cdk-lib must be exact, got {ver}"
