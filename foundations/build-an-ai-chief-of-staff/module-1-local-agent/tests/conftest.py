"""Shared fixtures and configuration for the Module 1 notebook test suite.

Two tiers:
  - FAST  (default): static checks, scripts, hooks — no model calls, no credentials.
  - SLOW  (`-m slow`): executes the real notebook against Amazon Bedrock via nbclient.

The slow tier auto-skips when AWS credentials are absent, so a bare `pytest` always
runs cleanly on a laptop with no setup.
"""
from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

import pytest

# ──────────────────────────────────────────────────────────── paths
MODULE_DIR = Path(__file__).resolve().parent.parent           # module-1-local-agent/
NOTEBOOK = MODULE_DIR / "module-1-local-agent.ipynb"
AGENT_DIR = MODULE_DIR / "chief_of_staff_agent"
CLAUDE_DIR = AGENT_DIR / ".claude"
AUDIT_DIR = AGENT_DIR / "audit"
REPORTS_DIR = AGENT_DIR / "output_reports"
SCRIPTS_DIR = AGENT_DIR / "scripts"


@pytest.fixture(scope="session")
def module_dir() -> Path:
    return MODULE_DIR


@pytest.fixture(scope="session")
def agent_dir() -> Path:
    return AGENT_DIR


# ──────────────────────────────────────────────────────────── slow-tier gating
def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "slow: executes the real notebook against Bedrock (needs AWS creds)")


def _aws_creds_available() -> bool:
    """True if STS reports a valid identity (so Bedrock calls can succeed)."""
    try:
        import boto3

        boto3.client("sts").get_caller_identity()
        return True
    except Exception:
        return False


@pytest.fixture(scope="session")
def aws_ready() -> bool:
    return _aws_creds_available()


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Skip every `slow` test if AWS credentials are not usable."""
    if _aws_creds_available():
        return
    skip = pytest.mark.skip(reason="AWS credentials not available — slow (live Bedrock) tests skipped")
    for item in items:
        if "slow" in item.keywords:
            item.add_marker(skip)


# ──────────────────────────────────────────────────────────── disk backup / restore
def _snapshot(paths: list[Path]) -> dict[Path, bytes | None]:
    """Capture current bytes of each file (None = absent), so we can restore later."""
    snap: dict[Path, bytes | None] = {}
    for p in paths:
        snap[p] = p.read_bytes() if p.exists() else None
    return snap


@pytest.fixture(scope="session")
def clean_workspace():
    """Back up audit logs + output_reports, yield, then restore so the repo stays pristine.

    The live notebook run mutates audit/*.json (hooks append) and writes a report into
    output_reports/. We snapshot those, let the run happen, then put everything back —
    `git status` should be clean after the suite.
    """
    tracked = [
        AUDIT_DIR / "script_usage_log.json",
        AUDIT_DIR / "report_history.json",
    ]
    snap = _snapshot(tracked)
    reports_before = set(REPORTS_DIR.glob("*")) if REPORTS_DIR.exists() else set()

    yield

    # restore tracked files
    for path, content in snap.items():
        if content is None:
            path.unlink(missing_ok=True)
        else:
            path.write_bytes(content)
    # remove any new files the agent wrote into output_reports/
    if REPORTS_DIR.exists():
        for p in set(REPORTS_DIR.glob("*")) - reports_before:
            if p.is_file():
                p.unlink()


# ──────────────────────────────────────────────────────────── executed-notebook fixture (slow)
@pytest.fixture(scope="session")
def executed_notebook(clean_workspace):
    """Execute the real notebook once via nbclient and return the resulting NotebookNode.

    `allow_errors=False` means any cell that raises fails the whole run — this *is* the
    top-to-bottom guarantee. Run path is the module dir so the notebook's relative
    `cwd="chief_of_staff_agent"` resolves correctly.
    """
    import nbformat
    from nbclient import NotebookClient

    nb = nbformat.read(NOTEBOOK, as_version=4)
    client = NotebookClient(
        nb,
        timeout=600,                         # generous per-cell ceiling for agent turns
        kernel_name="python3",               # resolved from the active (uv) venv
        resources={"metadata": {"path": str(MODULE_DIR)}},
        allow_errors=False,
    )
    client.execute()
    return nb


# ──────────────────────────────────────────────────────────── helpers shared by tests
def cell_text_outputs(cell) -> str:
    """Concatenate all textual output (stream text, text/plain, text/html) of a cell."""
    chunks: list[str] = []
    for out in cell.get("outputs", []):
        if out.get("output_type") == "stream":
            chunks.append(out.get("text", ""))
        elif out.get("output_type") in ("execute_result", "display_data"):
            data = out.get("data", {})
            chunks.append(data.get("text/plain", "") or "")
            chunks.append(data.get("text/html", "") or "")
        elif out.get("output_type") == "error":
            chunks.append("\n".join(out.get("traceback", [])))
    return "\n".join(chunks)


def code_cells(nb) -> list:
    return [c for c in nb.cells if c.cell_type == "code"]
