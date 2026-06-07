"""Shared fixtures + config for the Module 3 (memory) test suite.

Two tiers:
  - FAST (default): static checks on the entrypoint reuse + memory injection, the memory
    helper's graceful degradation, agentcore.json memories[], Dockerfile, notebook —
    no AWS, no Docker, no model calls.
  - SLOW (`-m slow`): real `agentcore deploy`/`invoke` round-trip that proves cross-session
    recall. Needs AWS creds + the agentcore CLI; auto-skipped when those are missing.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

MODULE_DIR = Path(__file__).resolve().parent.parent          # module-3-memory/
AGENT_DIR = MODULE_DIR / "chief_of_staff_agent"
AGENTCORE_DIR = MODULE_DIR / "agentcore"
MEMORY_DIR = AGENT_DIR / "memory"
NOTEBOOK = MODULE_DIR / "module-3-memory.ipynb"
MODULE1_AGENT = MODULE_DIR.parent / "module-1-local-agent" / "chief_of_staff_agent" / "agent.py"


@pytest.fixture(scope="session")
def module_dir() -> Path:
    return MODULE_DIR


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "slow: deploys/invokes against AWS AgentCore (creds)")


def _deploy_prereqs_ok() -> bool:
    """True only if everything a live deploy needs is present.

    Note: the agentcore Container build runs in the cloud (AWS CodeBuild, ARM64) — local Docker
    is NOT required to deploy. So we gate only on the agentcore CLI + valid AWS credentials.
    """
    if shutil.which("agentcore") is None:
        return False
    try:
        import boto3

        boto3.client("sts").get_caller_identity()
    except Exception:
        return False
    return True


def pytest_collection_modifyitems(config, items) -> None:
    if _deploy_prereqs_ok():
        return
    skip = pytest.mark.skip(reason="deploy prereqs missing (agentcore CLI / AWS creds)")
    for item in items:
        if "slow" in item.keywords:
            item.add_marker(skip)


def cell_text_outputs(cell) -> str:
    chunks = []
    for out in cell.get("outputs", []):
        if out.get("output_type") == "stream":
            chunks.append(out.get("text", ""))
        elif out.get("output_type") in ("execute_result", "display_data"):
            d = out.get("data", {})
            chunks.append(d.get("text/plain", "") or "")
        elif out.get("output_type") == "error":
            chunks.append("\n".join(out.get("traceback", [])))
    return "\n".join(chunks)
