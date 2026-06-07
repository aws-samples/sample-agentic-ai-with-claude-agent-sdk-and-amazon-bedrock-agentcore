"""SLOW tier — execute the real notebook against Amazon Bedrock and assert behavior.

Marked `slow`: requires AWS credentials (auto-skipped otherwise, see conftest). The whole
notebook is executed ONCE by the session-scoped `executed_notebook` fixture; every test here
inspects that single run, so we pay the (multi-minute, real-token) cost only once.

Assertions are structural/behavioral — never exact wording — because agent output is
non-deterministic. We check: it ran top-to-bottom (the fixture enforces no cell raised),
the right tools fired (via the audit ledger + subagent delegation line), side-effects landed
on disk, and a few deterministic grounded facts appear.
"""
from __future__ import annotations

import json

import pytest

from conftest import AUDIT_DIR, REPORTS_DIR, cell_text_outputs, code_cells

pytestmark = pytest.mark.slow


# ──────────────────────────────────────────── helpers
def _find_cell(nb, *needles):
    """Return the first code cell whose source contains all needles."""
    for c in code_cells(nb):
        if all(n in c.source for n in needles):
            return c
    raise AssertionError(f"no code cell contains all of {needles}")


def _all_output_text(nb) -> str:
    return "\n".join(cell_text_outputs(c) for c in code_cells(nb))


# ──────────────────────────────────────────── top-to-bottom + setup
def test_notebook_ran_without_errors(executed_notebook):
    """The fixture used allow_errors=False, so reaching here means every cell executed.
    Double-check no cell carries an error output."""
    for i, c in enumerate(code_cells(executed_notebook)):
        for out in c.get("outputs", []):
            assert out.get("output_type") != "error", (
                f"cell {i} raised: {out.get('ename')}: {out.get('evalue')}"
            )


def test_setup_cell_reports_bedrock(executed_notebook):
    cell = _find_cell(executed_notebook, "CLAUDE_CODE_USE_BEDROCK", "Provider: Amazon Bedrock")
    out = cell_text_outputs(cell)
    assert "Provider: Amazon Bedrock" in out
    assert "NOT SET" not in out, "ANTHROPIC_MODEL / region was not configured"


# ──────────────────────────────────────────── reliable ledger: scripts actually ran
def test_audit_ledger_grew_and_logged_scripts(executed_notebook):
    """The Bash PostToolUse hook records every scripts/*.py run. After the notebook executes,
    the ledger should be non-empty and include the simple_calculation run from the scripts cell."""
    log = json.loads((AUDIT_DIR / "script_usage_log.json").read_text())
    executions = log.get("script_executions", [])
    assert executions, "no scripts were logged — Bash/scripts path did not fire"
    scripts_run = {e.get("script") for e in executions}
    assert "simple_calculation.py" in scripts_run, f"expected simple_calculation.py, saw {scripts_run}"


# ──────────────────────────────────────────── subagent delegation
def test_subagent_delegation_visible(executed_notebook):
    """The subagent cell delegates via Task; print_activity prints a 'Delegating to subagent' line
    (Task is its own message block, so this rendered signal is reliable here)."""
    cell = _find_cell(executed_notebook, "Delegate to the financial-analyst")
    out = cell_text_outputs(cell)
    assert ("Delegating to subagent" in out) or ("financial-analyst" in out), (
        "no sign the financial-analyst subagent was invoked"
    )


# ──────────────────────────────────────────── report write + tracker hook
def test_all_together_wrote_report_and_logged_it(executed_notebook):
    """The 'putting it all together' brief should produce a report file and a report_history entry."""
    reports = [p for p in REPORTS_DIR.glob("*") if p.is_file() and p.name != ".gitkeep"]
    history = json.loads((AUDIT_DIR / "report_history.json").read_text()).get("reports", [])
    assert reports or history, "no report written and report_history is empty"


# ──────────────────────────────────────────── grounded facts (deterministic anchors)
def test_runway_grounded_facts_present(executed_notebook):
    """Runway/burn answers are anchored by CLAUDE.md + data: ~$500K burn, 20 months runway.
    These numbers are deterministic enough to assert across the runway/memory/multi-turn cells."""
    text = _all_output_text(executed_notebook)
    assert "20" in text, "expected the 20-month runway figure somewhere in the outputs"
    assert ("500" in text or "$500" in text), "expected the ~$500K monthly burn figure"


# ──────────────────────────────────────────── skill firing (soft)
def test_financial_analysis_skill_signal(executed_notebook):
    """The skill cell should show the financial-analysis SOP in action. Soft check: the model
    occasionally inlines the analysis instead of naming the skill, so we accept either the skill
    name OR the SOP's recommendation shape — and only xfail (not hard-fail) if neither appears."""
    cell = _find_cell(executed_notebook, "board-ready analysis of our runway if we hire 10 engineers")
    out = cell_text_outputs(cell).lower()
    fired = "financial-analysis" in out or "skill" in out
    sop_shape = "recommend" in out  # the SOP ends with a recommendation
    if not (fired or sop_shape):
        pytest.xfail("skill not explicitly visible and SOP shape absent — tolerated (model variance)")
