"""SLOW — real deploy, then a clarification round-trip (ask → answer + resume → answer).

Proves the serverless multi-round mechanism end-to-end: an ambiguous prompt yields a
`clarification_needed` block with an SDK session id; re-invoking with an answer + that
session id produces a final answer. Snapshots config so git stays clean; tears down.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess

import boto3
import pytest

from conftest import AGENTCORE_DIR, MODULE_DIR

pytestmark = pytest.mark.slow

REGION = os.environ.get("AWS_REGION", "us-west-2")
RUNTIME = "analytics"
STACK = "AgentCore-aafollowup-default"
_SNAPSHOT = ["agentcore.json", "aws-targets.json"]


def _run(cmd: list[str], timeout: int = 1500) -> str:
    p = subprocess.run(cmd, cwd=MODULE_DIR, capture_output=True, text=True, timeout=timeout)
    return p.stdout + p.stderr


def _json_blocks(text: str) -> list[dict]:
    out = []
    for m in re.findall(r"```json\s*(\{.*?\})\s*```", text, re.DOTALL):
        try:
            out.append(json.loads(m))
        except json.JSONDecodeError:
            pass
    return out


@pytest.fixture(scope="module")
def deployed():
    account = boto3.client("sts").get_caller_identity()["Account"]
    snap = {f: (AGENTCORE_DIR / f).read_text()
            for f in _SNAPSHOT if (AGENTCORE_DIR / f).exists()}
    (AGENTCORE_DIR / "aws-targets.json").write_text(
        json.dumps([{"name": "default", "account": account, "region": REGION}], indent=2)
    )
    dep = _run(["agentcore", "deploy", "-y"])
    try:
        assert "Deployed" in dep or "deploy" in dep.lower(), f"deploy failed:\n{dep[:2000]}"
        yield account
    finally:
        try:
            boto3.client("cloudformation", region_name=REGION).delete_stack(StackName=STACK)
        except Exception:
            pass
        for f, text in snap.items():
            (AGENTCORE_DIR / f).write_text(text)
        if "aws-targets.json" not in snap:
            (AGENTCORE_DIR / "aws-targets.json").write_text("[]\n")
        shutil.rmtree(AGENTCORE_DIR / ".cli" / "logs", ignore_errors=True)


def test_ambiguous_prompt_triggers_clarification(deployed):
    out = _run(["agentcore", "invoke", json.dumps({"prompt": "Show me the top students."}),
                "--runtime", RUNTIME, "--session-id", "agentic-analytics-m3-live-ask-0001"])
    clar = next((b for b in _json_blocks(out) if b.get("status") == "clarification_needed"), None)
    assert clar is not None, f"expected a clarification block, got:\n{out[:2000]}"
    assert clar.get("questions"), "clarification had no questions"
    assert clar.get("claude_agent_sdk_session_id"), "no SDK session id to resume with"


def test_answer_with_resume_yields_final_answer(deployed):
    # Round 1: get the clarification + session id.
    ask = _run(["agentcore", "invoke", json.dumps({"prompt": "Show me the top 5 students."}),
                "--runtime", RUNTIME, "--session-id", "agentic-analytics-m3-live-rt-0001"])
    blocks = _json_blocks(ask)
    clar = next((b for b in blocks if b.get("status") == "clarification_needed"), None)
    assert clar is not None, f"no clarification in round 1:\n{ask[:1500]}"
    sdk_session = clar["claude_agent_sdk_session_id"]

    # Round 2: answer (rank by GPA) and resume the session.
    ans = _run(["agentcore", "invoke",
                json.dumps({"prompt": "Rank them by GPA, all semesters.",
                            "claude_agent_sdk_session_id": sdk_session}),
                "--runtime", RUNTIME, "--session-id", "agentic-analytics-m3-live-rt-0001"])
    # A final answer should mention GPA and not be another clarification request.
    assert "clarification_needed" not in ans, f"still asking after an answer:\n{ans[:1500]}"
    assert re.search(r"gpa|\d\.\d", ans, re.IGNORECASE), f"no GPA-ranked answer:\n{ans[:1500]}"
