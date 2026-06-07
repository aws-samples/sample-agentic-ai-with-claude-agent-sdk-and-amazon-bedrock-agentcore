"""SLOW — real agentcore deploy → invoke round-trip, then teardown.

Deploys the agent, invokes it with a question whose answer is known from the demo
data, asserts the answer mentions the count, then destroys the stack. Snapshots
the config files the deploy mutates so `git status` stays clean afterward.

Needs: agentcore CLI + AWS creds + a CDK-bootstrapped account + the Module 0
infra. Auto-skipped (via conftest) when prereqs are missing.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

import boto3
import pytest

from conftest import AGENTCORE_DIR, MODULE_DIR

pytestmark = pytest.mark.slow

REGION = os.environ.get("AWS_REGION", "us-west-2")
SESSION_ID = "agentic-analytics-m2-livetest-session-0001"  # ≥33 chars
_SNAPSHOT_FILES = ["agentcore.json", "aws-targets.json"]


def _run(cmd: list[str], timeout: int = 1500) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=MODULE_DIR, capture_output=True, text=True, timeout=timeout)


@pytest.fixture(scope="module")
def deployed():
    account = boto3.client("sts").get_caller_identity()["Account"]
    # Snapshot tracked config the deploy will mutate, so we can restore it.
    snap = {f: (AGENTCORE_DIR / f).read_text()
            for f in _SNAPSHOT_FILES if (AGENTCORE_DIR / f).exists()}
    (AGENTCORE_DIR / "aws-targets.json").write_text(
        json.dumps([{"name": "default", "account": account, "region": REGION}], indent=2)
    )

    dep = _run(["agentcore", "deploy", "-y"])
    try:
        assert dep.returncode == 0, f"deploy failed:\n{dep.stdout}\n{dep.stderr}"
        yield {"account": account, "deploy_out": dep.stdout}
    finally:
        # Teardown: destroy the stack directly (most reliable).
        try:
            boto3.client("cloudformation", region_name=REGION).delete_stack(
                StackName="AgentCore-aaanalytics-default"
            )
        except Exception:
            pass
        # Restore tracked config + drop local-only files so git stays clean.
        for f, text in snap.items():
            (AGENTCORE_DIR / f).write_text(text)
        if "aws-targets.json" not in snap:
            (AGENTCORE_DIR / "aws-targets.json").write_text("[]\n")
        shutil.rmtree(AGENTCORE_DIR / ".cli" / "logs", ignore_errors=True)


def test_deploy_succeeded(deployed):
    assert "deploy" in deployed["deploy_out"].lower() or deployed["deploy_out"]


def test_invoke_returns_known_count(deployed):
    out = _run(
        ["agentcore", "invoke",
         json.dumps({"prompt": "Count every distinct student_id in the "
                     "student_enrollment_analytics table — the grand total across all "
                     "semesters, with no status or semester filters. Give the number."}),
         "--session-id", SESSION_ID],
    )
    text = out.stdout + out.stderr
    # 10,000 distinct student_ids across the whole demo table — tolerant of formatting.
    assert "10,000" in text or "10000" in text, f"unexpected invoke output:\n{text[:2000]}"
