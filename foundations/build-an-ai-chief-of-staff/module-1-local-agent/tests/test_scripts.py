"""FAST checks — the agent's Python scripts run deterministically and return expected values.

These are the tools the agent calls via Bash. They use only stdlib and print JSON, so we can
assert exact numbers with no model in the loop. This guards the scripts the notebook depends on.
"""
from __future__ import annotations

import json
import subprocess
import sys

import pytest

from conftest import AGENT_DIR, SCRIPTS_DIR


def _run(script: str, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPTS_DIR / script), *args],
        cwd=str(AGENT_DIR),
        capture_output=True,
        text=True,
    )


def _first_json_object(text: str) -> dict:
    """Parse the first JSON object in stdout. Some scripts print JSON then a text summary."""
    start = text.index("{")
    obj, _ = json.JSONDecoder().raw_decode(text[start:])
    return obj


def test_simple_calculation_runway():
    """$10M cash / $500K burn = exactly 20 months runway (matches CLAUDE.md)."""
    proc = _run("simple_calculation.py", "10000000", "500000")
    assert proc.returncode == 0, proc.stderr
    data = _first_json_object(proc.stdout)
    assert data["runway_months"] == 20.0
    assert data["monthly_burn"] == 500000.0


def test_hiring_impact_reduces_runway():
    """Hiring 10 engineers increases burn and shortens runway from the 20-month baseline."""
    proc = _run("hiring_impact.py", "10")
    assert proc.returncode == 0, proc.stderr
    data = _first_json_object(proc.stdout)
    assert data["num_engineers"] == 10
    assert data["total_monthly_increase"] > 0
    assert data["new_runway_months"] < data["current_runway_months"]


def test_financial_forecast_json():
    """--format json yields a parseable forecast with the current ARR baseline."""
    proc = _run("financial_forecast.py", "--arr", "2400000", "--growth", "0.15",
                "--months", "6", "--format", "json")
    assert proc.returncode == 0, proc.stderr
    data = _first_json_object(proc.stdout)
    assert isinstance(data, dict) and data, "forecast produced no JSON object"


@pytest.mark.parametrize("script", [
    "simple_calculation.py",
    "financial_forecast.py",
    "hiring_impact.py",
    "decision_matrix.py",
    "talent_scorer.py",
])
def test_script_runs_without_crashing(script):
    """Every script runs with its defaults (or a usage message) and never crashes hard."""
    proc = _run(script) if script != "simple_calculation.py" else _run(script, "10000000", "500000")
    if script == "hiring_impact.py":
        proc = _run(script, "5")
    # exit 0 (ran) or exit 1 (printed a usage/arg message) are both acceptable; a crash is not.
    assert proc.returncode in (0, 1), f"{script} crashed: {proc.stderr}"
    assert proc.stdout.strip(), f"{script} produced no output"
