"""Shared fixtures + config for the Module 1 (local agent) test suite.

FAST (default): static checks on agent.py + bundle + notebook (no creds, no model).
SLOW (`-m slow`): runs the agent against Bedrock + Athena; auto-skipped without creds.
"""
from __future__ import annotations

from pathlib import Path

import pytest

MODULE_DIR = Path(__file__).resolve().parent.parent          # module-1-local-agent/
AGENT_DIR = MODULE_DIR / "analytics_agent"
NOTEBOOK = MODULE_DIR / "module-1-local-agent.ipynb"


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "slow: runs the agent against Bedrock + Athena")


def _creds_ok() -> bool:
    try:
        import boto3

        boto3.client("sts").get_caller_identity()
    except Exception:
        return False
    return True


def pytest_collection_modifyitems(config, items) -> None:
    if _creds_ok():
        return
    skip = pytest.mark.skip(reason="AWS creds missing — slow agent test skipped")
    for item in items:
        if "slow" in item.keywords:
            item.add_marker(skip)
