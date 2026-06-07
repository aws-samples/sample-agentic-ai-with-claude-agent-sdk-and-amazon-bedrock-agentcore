"""Shared fixtures + config for the Module 0 (setup) test suite.

Two tiers:
  - FAST (default): static checks on the script + notebook — no AWS, no creds.
  - SLOW (`-m slow`): runs the real infra `verify()` against AWS (S3 + Athena);
    auto-skipped when AWS credentials are missing.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

MODULE_DIR = Path(__file__).resolve().parent.parent      # module-0-setup/
SCRIPTS_DIR = MODULE_DIR / "scripts"
NOTEBOOK = MODULE_DIR / "module-0-setup.ipynb"


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "slow: creates/queries real AWS infra (S3 + Athena)")


def _aws_creds_ok() -> bool:
    try:
        import boto3

        boto3.client("sts", region_name=_region()).get_caller_identity()
    except Exception:
        return False
    return True


def _region() -> str:
    return os.environ.get("AWS_REGION") or "us-west-2"


def pytest_collection_modifyitems(config, items) -> None:
    if _aws_creds_ok():
        return
    skip = pytest.mark.skip(reason="AWS creds missing — slow infra test skipped")
    for item in items:
        if "slow" in item.keywords:
            item.add_marker(skip)
