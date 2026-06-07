"""SLOW — real deploy + cross-session recall round-trip against AWS AgentCore.

Marked `slow`; auto-skipped unless the agentcore CLI + AWS creds are present (see
conftest._deploy_prereqs_ok). The Container image builds in the cloud (CodeBuild, ARM64),
so local Docker is NOT required. This deploys real infrastructure (runtime + a CosMemory
resource), costs money, and takes ~10 min.

What it proves (the Module 3 thesis):
  1. deploy succeeds and provisions BOTH a runtime and the memory resource;
  2. create_event actually works post-deploy (no AccessDenied — i.e. the CDK auto-wired the
     memory data-plane IAM, as the Phase-0 spike found);
  3. SHORT-TERM cross-session recall: a fact stated in session A is recalled in a NEW
     session B for the same actor (this rides on list_events, so it's reliable immediately —
     it does NOT wait on async long-term extraction).

The fixture deploys ONCE, ALWAYS tears down (runtime + memory) so nothing lingers, and
restores the tracked config files it mutated so `git status` stays clean.
"""
from __future__ import annotations

import json
import re
import subprocess

import pytest

from conftest import AGENTCORE_DIR, MODULE_DIR

pytestmark = pytest.mark.slow

_ANSI = re.compile(r"\x1b\[[0-9;?]*[a-zA-Z]")

# An actor + an invented fact that is NOT in the bundle's CLAUDE.md (which hardcodes a
# $30M Series B). Recall of THIS value can only come from memory, not always-on context.
ACTOR = "techstart-cos"
INVENTED_FACT_PROMPT = (
    "Note for the record: we are modeling our Series B raise at a $42.5M target "
    "with an 18-month bridge."
)
RECALL_PROMPT = "What raise target did we land on for the Series B?"


def _parse_json_line(text: str) -> dict:
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
    config_files = [AGENTCORE_DIR / "agentcore.json", AGENTCORE_DIR / "aws-targets.json"]
    snapshot = {p: p.read_text() for p in config_files if p.exists()}

    dep = _run("deploy", "-y", "--json")
    assert dep.returncode == 0, f"deploy failed:\n{dep.stdout}\n{dep.stderr}"
    try:
        yield dep.stdout
    finally:
        _run("remove", "agent", "--name", "cos")
        _run("remove", "memory", "--name", "CosMemory")
        _run("deploy", "-y")  # apply teardown (destroys runtime + memory)
        for path, text in snapshot.items():
            path.write_text(text)


def test_deploy_provisioned_runtime_and_memory(deployed_agent):
    out = _parse_json_line(deployed_agent)
    assert out.get("success") is True
    blob = json.dumps(out.get("outputs", out))
    assert "runtime/" in blob, f"no runtime ARN in deploy outputs: {out.get('outputs')}"


def test_cross_session_recall(deployed_agent):
    """Session A states an invented fact; a NEW session B recalls it. Proves cross-session
    memory: B shares no transcript with A, and the value isn't in CLAUDE.md."""
    sess_a = "sess-m3-live-session-a-0000000000001"   # >=33 chars
    sess_b = "sess-m3-live-session-b-0000000000002"

    write = _run("invoke", "--session-id", sess_a, INVENTED_FACT_PROMPT, timeout=300)
    combined = (write.stdout or "") + (write.stderr or "")
    # The container's create_event must not be denied — proves IAM is wired.
    assert "AccessDenied" not in combined and "Permission denied" not in combined, combined[-800:]

    recall = _run("invoke", "--session-id", sess_b, RECALL_PROMPT, timeout=300)
    rcombined = (recall.stdout or "") + (recall.stderr or "")
    assert "AccessDenied" not in rcombined, rcombined[-800:]
    # The invented figure can only be present if memory recalled session A.
    assert "42.5" in rcombined, (
        "agent did not recall the $42.5M figure from the prior session — cross-session "
        f"memory not working. Output tail:\n{rcombined[-800:]}"
    )
