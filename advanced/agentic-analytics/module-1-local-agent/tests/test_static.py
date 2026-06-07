"""FAST — static checks on the bundle layout + notebook. No creds."""
from __future__ import annotations

import ast

import nbformat
import pytest

from conftest import AGENT_DIR, NOTEBOOK


def test_bundle_has_required_files():
    assert (AGENT_DIR / "agent.py").exists()
    assert (AGENT_DIR / "CLAUDE.md").exists()
    assert (AGENT_DIR / "tools" / "athena_tools.py").exists()
    assert (AGENT_DIR / "tools" / "sql_validator.py").exists()


def test_skills_present():
    skills = AGENT_DIR / ".claude" / "skills"
    assert (skills / "enrollment" / "SKILL.md").exists()
    assert (skills / "financial" / "SKILL.md").exists()


def test_metadata_present():
    md = AGENT_DIR / "data" / "metadata"
    for t in ("student_enrollment_analytics", "financial_summary_by_student"):
        assert (md / f"{t}.yaml").exists()
        assert (md / f"{t}_sample_data.csv").exists()


def test_claude_md_skill_names_are_not_stale():
    """CLAUDE.md must reference skills that actually exist on disk (the old one didn't)."""
    text = (AGENT_DIR / "CLAUDE.md").read_text()
    assert "enrollment" in text and "financial" in text
    # the stale names from the old bundle must be gone
    assert "academic-performance" not in text
    assert "enrollment-analytics" not in text
    assert "financial-analytics" not in text


def _strip_shell_lines(source: str) -> str:
    """Blank out IPython shell-escape (!) / magic (%) lines, including backslash
    line-continuations, so the rest parses as plain Python."""
    out, skipping = [], False
    for line in source.splitlines():
        if skipping:
            out.append("")
            skipping = line.rstrip().endswith("\\")
            continue
        if line.lstrip().startswith(("!", "%")):
            out.append("")
            skipping = line.rstrip().endswith("\\")
        else:
            out.append(line)
    return "\n".join(out)


@pytest.mark.skipif(not NOTEBOOK.exists(), reason="notebook not created yet")
def test_notebook_code_cells_parse():
    nb = nbformat.read(NOTEBOOK, as_version=4)
    for i, cell in enumerate(nb.cells):
        if cell.cell_type != "code":
            continue
        try:
            ast.parse(_strip_shell_lines(cell.source))
        except SyntaxError as e:
            pytest.fail(f"cell {i} failed to parse: {e}")


@pytest.mark.skipif(not NOTEBOOK.exists(), reason="notebook not created yet")
def test_notebook_teaches_skills_contrast():
    """The notebook tells the 1a (no skills) → 1b (with skills) story."""
    nb = nbformat.read(NOTEBOOK, as_version=4)
    text = "\n".join(c.source for c in nb.cells).lower()
    assert "without skills" in text or "no skills" in text
    assert "with skills" in text
