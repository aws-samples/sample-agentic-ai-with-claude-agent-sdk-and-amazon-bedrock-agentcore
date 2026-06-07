"""SLOW — run the real local agent once against Bedrock + Athena.

Structural assertion (tolerant of model nondeterminism): the agent should run an
Athena query and surface a count consistent with the known data. Auto-skipped
without creds. Requires Module 0's infra to exist.
"""
from __future__ import annotations

import asyncio
import os
import sys

import pytest

from conftest import AGENT_DIR

sys.path.insert(0, str(AGENT_DIR))

pytestmark = pytest.mark.slow


def test_agent_answers_a_count_question():
    import boto3

    import agent

    os.environ.setdefault("CLAUDE_CODE_USE_BEDROCK", "1")
    os.environ.setdefault("AWS_REGION", "us-west-2")
    os.environ.setdefault("ATHENA_DATABASE", "student_analytics")
    acct = boto3.client("sts").get_caller_identity()["Account"]
    os.environ.setdefault(
        "ATHENA_OUTPUT_LOCATION",
        f"s3://student-analytics-agent-{acct}/athena-results/",
    )

    result, messages = asyncio.run(
        agent.run_query(
            "How many distinct students are in the enrollment table? "
            "Give me the single number.",
            request_id="m1-live-test",
        )
    )

    text = (result or "") + "\n".join(
        getattr(b, "text", "")
        for m in messages
        for b in (getattr(m, "content", []) or [])
    )
    # 10,000 distinct students in student_enrollment_analytics (per the demo data).
    assert "10,000" in text or "10000" in text
