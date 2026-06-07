"""FAST checks — the PostToolUse hooks append correctly to the audit ledger.

The hooks read a PostToolUse payload `{tool_name, tool_input, tool_response}` on stdin and append
to `../../audit/<file>.json` (relative to the hook file). We copy each hook into a temp
`.claude/hooks/` tree with an empty-skeleton `audit/`, feed it a synthetic payload, and assert the
ledger gained the right entry. This proves the hook contract — including the empty-skeleton append
path — without invoking the agent.

Hooks always `sys.exit(0)` (they must never break a tool call), so we assert on file content, not
exit code.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import CLAUDE_DIR


def _hook_sandbox(tmp_path: Path, hook_name: str, audit_filename: str, skeleton: dict) -> tuple[Path, Path]:
    """Recreate the .claude/hooks + audit layout in tmp; return (hook_copy, audit_file)."""
    hooks_dir = tmp_path / ".claude" / "hooks"
    audit_dir = tmp_path / "audit"
    hooks_dir.mkdir(parents=True)
    audit_dir.mkdir(parents=True)

    hook_copy = hooks_dir / hook_name
    shutil.copy(CLAUDE_DIR / "hooks" / hook_name, hook_copy)

    audit_file = audit_dir / audit_filename
    audit_file.write_text(json.dumps(skeleton))
    return hook_copy, audit_file


def _feed(hook_copy: Path, payload: dict) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(hook_copy)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
    )


def test_script_usage_logger_appends_entry(tmp_path):
    hook, audit = _hook_sandbox(
        tmp_path, "script-usage-logger.py", "script_usage_log.json",
        {"script_executions": []},
    )
    payload = {
        "tool_name": "Bash",
        "tool_input": {"command": "python scripts/simple_calculation.py 10000000 500000",
                       "description": "runway calc"},
        "tool_response": {"success": True},
    }
    proc = _feed(hook, payload)
    assert proc.returncode == 0

    data = json.loads(audit.read_text())
    assert len(data["script_executions"]) == 1
    entry = data["script_executions"][0]
    assert entry["script"] == "simple_calculation.py"
    assert entry["tool_used"] == "Bash"


def test_script_usage_logger_ignores_non_script_bash(tmp_path):
    """A plain Bash command (not a scripts/*.py run) should not be logged."""
    hook, audit = _hook_sandbox(
        tmp_path, "script-usage-logger.py", "script_usage_log.json",
        {"script_executions": []},
    )
    proc = _feed(hook, {"tool_name": "Bash", "tool_input": {"command": "ls -la"}, "tool_response": {}})
    assert proc.returncode == 0
    assert json.loads(audit.read_text())["script_executions"] == []


def test_report_tracker_appends_entry(tmp_path):
    hook, audit = _hook_sandbox(
        tmp_path, "report-tracker.py", "report_history.json",
        {"reports": []},
    )
    payload = {
        "tool_name": "Write",
        "tool_input": {"file_path": "output_reports/strategic_brief.md",
                       "content": "Runway is 20 months. Recommendation: hire in phases."},
        "tool_response": {"success": True},
    }
    proc = _feed(hook, payload)
    assert proc.returncode == 0

    data = json.loads(audit.read_text())
    assert len(data["reports"]) == 1
    entry = data["reports"][0]
    assert entry["file"] == "strategic_brief.md"
    assert entry["action"] == "created"
    assert entry["tool"] == "Write"
