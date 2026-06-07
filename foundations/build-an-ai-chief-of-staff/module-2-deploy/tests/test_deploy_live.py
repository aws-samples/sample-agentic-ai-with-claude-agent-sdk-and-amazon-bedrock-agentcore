"""SLOW — real deploy + invoke round-trip against AWS AgentCore.

Marked `slow`; auto-skipped unless the agentcore CLI + AWS creds are present (see
conftest._deploy_prereqs_ok). The Container image is built in the cloud (CodeBuild, ARM64), so
local Docker is NOT required. This deploys real infrastructure, costs money, and takes ~10 min.

The fixture deploys ONCE, runs the assertions, ALWAYS tears down so nothing lingers, and restores
the tracked config files it mutated.
"""
from __future__ import annotations

import json
import re
import subprocess

import pytest

from conftest import AGENTCORE_DIR, MODULE_DIR

pytestmark = pytest.mark.slow

_ANSI = re.compile(r"\x1b\[[0-9;?]*[a-zA-Z]")


def _parse_json_line(text: str) -> dict:
    """Extract the JSON object from `agentcore --json` output.

    The CLI mixes spinner/ANSI control sequences into the stream, so the JSON is not
    reliably the last line. Strip ANSI and find the line that parses as a dict.
    """
    for line in reversed(_ANSI.sub("", text).splitlines()):
        line = line.strip()
        if line.startswith("{") and line.endswith("}"):
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                continue
    raise AssertionError(f"no JSON object found in agentcore output:\n{text[-500:]}")


def _run(*args, timeout=900):
    return subprocess.run(
        ["agentcore", *args], cwd=str(MODULE_DIR),
        capture_output=True, text=True, timeout=timeout,
    )


@pytest.fixture(scope="module")
def deployed_agent():
    """Deploy the agent, yield, then tear down (remove agent + deploy).

    `agentcore remove`/`deploy` mutate the tracked config files (agentcore.json,
    aws-targets.json). We snapshot and restore them so the run leaves the repo as it
    found it — `git status` stays clean.
    """
    config_files = [
        AGENTCORE_DIR / "agentcore.json",
        AGENTCORE_DIR / "aws-targets.json",
    ]
    snapshot = {p: p.read_text() for p in config_files if p.exists()}

    dep = _run("deploy", "-y", "--json")
    assert dep.returncode == 0, f"deploy failed:\n{dep.stdout}\n{dep.stderr}"
    try:
        yield dep.stdout
    finally:
        _run("remove", "agent", "--name", "cos")
        _run("deploy", "-y")  # apply teardown (destroys the runtime/stack)
        for path, text in snapshot.items():
            path.write_text(text)  # restore tracked config


def test_deploy_succeeded(deployed_agent):
    out = _parse_json_line(deployed_agent)
    assert out.get("success") is True
    # a runtime ARN should be among the outputs
    arns = [v for v in out.get("outputs", {}).values() if "runtime/" in str(v)]
    assert arns, f"no runtime ARN in deploy outputs: {out.get('outputs')}"


def test_invoke_returns_answer(deployed_agent):
    """The deployed agent answers a runway question — and crucially does NOT hit the CodeZip
    'Permission denied' bundled-binary failure (the whole reason we use Container)."""
    res = _run("invoke", "What is our current runway?", timeout=300)
    combined = (res.stdout or "") + (res.stderr or "")
    assert "Permission denied" not in combined, "bundled-binary perms failure — container build is wrong"
    assert "Failed to start Claude Code" not in combined
    # grounded fact from CLAUDE.md (20-month runway). Soft: model phrasing varies.
    assert "20" in combined or "runway" in combined.lower()
