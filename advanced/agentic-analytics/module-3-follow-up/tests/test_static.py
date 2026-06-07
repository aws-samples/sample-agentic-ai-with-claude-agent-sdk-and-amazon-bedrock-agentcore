"""FAST — static checks on the follow-up notebook. No creds."""
from __future__ import annotations

import ast

import nbformat
import pytest

from conftest import NOTEBOOK


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
def test_notebook_teaches_clarification():
    nb = nbformat.read(NOTEBOOK, as_version=4)
    text = "\n".join(c.source for c in nb.cells).lower()
    assert "askuserquestion" in text or "clarification" in text or "follow-up" in text
    assert "resume" in text or "session" in text          # multi-round continuity
    assert "invoke_agentcore" in text                      # the driver
