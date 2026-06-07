"""Shared fixtures + config for the Module 3 (follow-up) test suite.

FAST (default): reuse/drift-guard + clarification wiring + config + notebook. No AWS.
SLOW (`-m slow`): real deploy + a clarification round-trip. Needs CLI + creds.
"""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest

MODULE_DIR = Path(__file__).resolve().parent.parent          # module-3-follow-up/
AGENT_DIR = MODULE_DIR / "analytics_agent"
AGENTCORE_DIR = MODULE_DIR / "agentcore"
SCRIPTS_DIR = MODULE_DIR / "scripts"
NOTEBOOK = MODULE_DIR / "module-3-follow-up.ipynb"
MODULE1_AGENT = (
    MODULE_DIR.parent / "module-1-local-agent" / "analytics_agent" / "agent.py"
)


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "slow: deploys + clarification round-trip on AWS")


def _deploy_prereqs_ok() -> bool:
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
