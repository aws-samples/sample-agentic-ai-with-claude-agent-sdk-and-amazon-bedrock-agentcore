"""SLOW — real end-to-end: enable Transaction Search → deploy → invoke → confirm OTEL is active.

Marked `slow`; auto-skipped without the agentcore CLI + AWS creds. Deploys real infra, costs money,
and is slow (deploy ~10 min). The fixture deploys ONCE, always tears down, and restores tracked config.

What this CAN assert automatically:
  - deploy succeeds (the CDK/CodeZip path is sound)
  - invoke works (no bundled-binary failure)
  - the container is running under `opentelemetry-instrument` (ADOT is emitting) — verified from the
    runtime logs (`opentelemetry.instrumentation` markers)

What it CANNOT assert automatically: spans landing in `/aws/spans`. That requires the per-runtime
**Tracing toggle**, which is a console action with no public CLI/API (see the notebook's Step 3). The
span check below is therefore **best-effort**: it reports whether spans were found, but does NOT fail the
test when the toggle is off (the common CI case).
"""
from __future__ import annotations

import json
import re
import subprocess
import time

import boto3
import pytest

from conftest import AGENT_DIR, AGENTCORE_DIR, MODULE_DIR, SCRIPTS_DIR

pytestmark = pytest.mark.slow

_ANSI = re.compile(r"\x1b\[[0-9;?]*[a-zA-Z]")
SESSION_ID = "m4-test-session-001"


def _agentcore(*args, timeout=1200):
    return subprocess.run(["agentcore", *args], cwd=str(MODULE_DIR),
                          capture_output=True, text=True, timeout=timeout)


def _parse_json_line(text: str) -> dict:
    for line in reversed(_ANSI.sub("", text).splitlines()):
        line = line.strip()
        if line.startswith("{") and line.endswith("}"):
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                continue
    raise AssertionError(f"no JSON object in output:\n{text[-500:]}")


def _region() -> str:
    return json.load(open(AGENTCORE_DIR / "aws-targets.json"))[0]["region"]


@pytest.fixture(scope="module")
def observable_deploy():
    """Enable Transaction Search, deploy, yield deploy outputs, then tear down + restore config."""
    region = _region()
    ts = subprocess.run(["python", str(SCRIPTS_DIR / "enable_transaction_search.py"), "--region", region],
                        cwd=str(MODULE_DIR), capture_output=True, text=True, timeout=120)
    assert ts.returncode == 0, f"enable_transaction_search failed:\n{ts.stdout}\n{ts.stderr}"

    config_files = [AGENTCORE_DIR / "agentcore.json", AGENTCORE_DIR / "aws-targets.json"]
    snapshot = {p: p.read_text() for p in config_files if p.exists()}

    dep = _agentcore("deploy", "-y", "--json")
    assert dep.returncode == 0, f"deploy failed:\n{dep.stdout}\n{dep.stderr}"
    try:
        yield {"deploy_out": dep.stdout, "region": region}
    finally:
        _agentcore("remove", "agent", "--name", "cos")
        _agentcore("deploy", "-y")
        for path, text in snapshot.items():
            path.write_text(text)


def test_deploy_succeeded(observable_deploy):
    out = _parse_json_line(observable_deploy["deploy_out"])
    assert out.get("success") is True
    arns = [v for v in out.get("outputs", {}).values() if "runtime/" in str(v)]
    assert arns, f"no runtime ARN: {out.get('outputs')}"


def test_invoke_works_and_otel_active(observable_deploy):
    """Invoke the agent; confirm it runs (no bundled-binary failure) AND that the container is
    instrumented with OpenTelemetry (ADOT) — the prerequisite for any trace to be emitted."""
    region = observable_deploy["region"]

    res = _agentcore("invoke", "--session-id", SESSION_ID, "What is our current runway?", timeout=300)
    combined = (res.stdout or "") + (res.stderr or "")
    assert "Permission denied" not in combined and "Failed to start Claude Code" not in combined

    # Confirm opentelemetry-instrument actually wrapped the process, from the runtime logs.
    logs = boto3.client("logs", region_name=region)
    groups = logs.describe_log_groups(
        logGroupNamePrefix="/aws/bedrock-agentcore/runtimes/cosobserve"
    )["logGroups"]
    assert groups, "no runtime log group — did the agent start?"
    newest = sorted(groups, key=lambda g: g.get("creationTime", 0))[-1]["logGroupName"]

    otel_active = False
    deadline = time.time() + 180  # logs can lag a bit after invoke
    while time.time() < deadline and not otel_active:
        for s in logs.describe_log_streams(logGroupName=newest, orderBy="LastEventTime",
                                           descending=True, limit=5).get("logStreams", []):
            for e in logs.get_log_events(logGroupName=newest, logStreamName=s["logStreamName"],
                                         limit=100, startFromHead=False).get("events", []):
                if "opentelemetry" in e["message"].lower():
                    otel_active = True
                    break
            if otel_active:
                break
        if not otel_active:
            time.sleep(20)
    assert otel_active, "no opentelemetry markers in runtime logs — ADOT wrapper not active"


def test_spans_delivered_best_effort(observable_deploy):
    """BEST-EFFORT: spans reach /aws/spans only if the per-runtime Tracing toggle is on (a console
    action — see notebook Step 3). This does NOT fail when the toggle is off; it just reports."""
    region = observable_deploy["region"]
    logs = boto3.client("logs", region_name=region)
    found = False
    try:
        qid = logs.start_query(
            logGroupName="aws/spans",
            startTime=int(time.time()) - 3600, endTime=int(time.time()),
            queryString=(f"fields @timestamp, attributes.session.id, name "
                         f"| filter attributes.session.id = '{SESSION_ID}' | limit 20"),
        )["queryId"]
        while True:
            r = logs.get_query_results(queryId=qid)
            if r["status"] in ("Complete", "Failed", "Cancelled"):
                break
            time.sleep(2)
        found = bool(r.get("results"))
    except logs.exceptions.ResourceNotFoundException:
        found = False

    if found:
        print(f"✅ spans for session {SESSION_ID} found in /aws/spans (Tracing toggle is ON)")
    else:
        pytest.skip("no spans in /aws/spans — enable the per-runtime Tracing toggle (notebook Step 3) "
                    "to deliver traces; this is expected when the toggle is off")
