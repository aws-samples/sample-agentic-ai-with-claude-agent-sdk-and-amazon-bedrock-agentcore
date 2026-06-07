"""Shared fixtures + config for the Module 4 (observability) test suite.

Two tiers:
  - FAST (default): drift-guard, config, Dockerfile, notebook, the Transaction Search helper — no AWS.
  - SLOW (`-m slow`): enable Transaction Search → deploy → invoke(session) → assert a span appears →
    teardown. Needs the agentcore CLI + AWS creds (the Container image builds in the cloud, so local
    Docker is not required). Auto-skipped when prereqs are missing.
"""
from __future__ import annotations

from pathlib import Path

import pytest

MODULE_DIR = Path(__file__).resolve().parent.parent          # module-4-observability/
AGENT_DIR = MODULE_DIR / "chief_of_staff_agent"
AGENTCORE_DIR = MODULE_DIR / "agentcore"
SCRIPTS_DIR = MODULE_DIR / "scripts"
NOTEBOOK = MODULE_DIR / "module-4-observability.ipynb"
MODULE1_AGENT = MODULE_DIR.parent / "module-1-local-agent" / "chief_of_staff_agent" / "agent.py"


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "slow: deploys/invokes against AWS + waits for traces (creds)")


def _deploy_prereqs_ok() -> bool:
    """agentcore CLI + valid AWS creds. (Container build runs in cloud CodeBuild — no local Docker.)"""
    import shutil

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
