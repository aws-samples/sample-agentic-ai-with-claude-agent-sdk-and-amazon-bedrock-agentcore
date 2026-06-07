"""SLOW — validate the real infra against AWS by reusing the script's verify().

This is the dev/CI mirror of what the participant sees: the SAME verify()
that prints the ✅ checklist is asserted on here. Auto-skipped without creds.
Assumes `setup_infrastructure.setup()` has been run (or runs it first).
"""
from __future__ import annotations

import os

import pytest

import setup_infrastructure as infra

pytestmark = pytest.mark.slow

REGION = os.environ.get("AWS_REGION", "us-west-2")


@pytest.fixture(scope="module")
def infra_result():
    # Idempotent: builds anything missing, then returns the verified state.
    return infra.setup(region=REGION)


def test_bucket_exists(infra_result):
    assert infra_result["bucket_ok"] is True


def test_database_exists(infra_result):
    assert infra_result["database_ok"] is True


def test_tables_have_expected_rows(infra_result):
    tables = infra_result["tables"]
    assert tables["student_enrollment_analytics"] == 50000
    assert tables["financial_summary_by_student"] == 10000


def test_overall_ok(infra_result):
    assert infra_result["ok"] is True
