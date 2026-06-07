"""FAST — static checks on the deploy notebook. No creds."""
from __future__ import annotations

import ast

import nbformat
import pytest

from conftest import NOTEBOOK


def _strip_shell_lines(source: str) -> str:
    """Blank out IPython shell-escape (!) / magic (%) lines, including their
    backslash line-continuations, so the rest parses as plain Python."""
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
def test_notebook_teaches_full_cli_lifecycle():
    """The notebook walks create → deploy → invoke → traces (not deploy-only)."""
    nb = nbformat.read(NOTEBOOK, as_version=4)
    text = "\n".join(c.source for c in nb.cells)
    for cmd in ("agentcore create", "agentcore deploy", "agentcore invoke", "agentcore traces"):
        assert cmd in text, f"notebook should teach `{cmd}`"


@pytest.mark.skipif(not NOTEBOOK.exists(), reason="notebook not created yet")
def test_notebook_explains_reuse_and_observability():
    nb = nbformat.read(NOTEBOOK, as_version=4)
    text = "\n".join(c.source for c in nb.cells).lower()
    assert "build_agent_options" in text          # reuse story
    assert "enableotel" in text or "enable_otel" in text or "transaction search" in text
    assert "session id" in text or "session-id" in text   # the ≥33-char gotcha
