"""FAST — notebook hygiene for module-3-memory.ipynb."""
from __future__ import annotations

import ast

import nbformat
import pytest

from conftest import NOTEBOOK


@pytest.fixture(scope="module")
def nb():
    return nbformat.read(NOTEBOOK, as_version=4)


def test_notebook_valid(nb):
    nbformat.validate(nb)


def test_code_cells_parse(nb):
    for i, c in enumerate(nb.cells):
        if c.cell_type != "code":
            continue
        # Skip IPython line magics / shell escapes (e.g. `!agentcore deploy`, `%cd`) —
        # they're valid in a notebook kernel but not parseable as Python.
        lines = [ln for ln in c.source.splitlines() if not ln.lstrip().startswith(("!", "%"))]
        wrapped = "async def _():\n" + "\n".join("    " + ln for ln in lines)
        try:
            ast.parse(wrapped)
        except SyntaxError:
            ast.parse("\n".join(lines))


def test_teaches_memory_flow(nb):
    md = "\n".join(c.source for c in nb.cells if c.cell_type == "markdown")
    for needle in ["agentcore deploy", "agentcore invoke", "Memory",
                   "session", "cross-session", "remove memory"]:
        assert needle in md, f"notebook should mention {needle!r}"


def test_teaches_short_vs_long_term(nb):
    md = "\n".join(c.source for c in nb.cells if c.cell_type == "markdown")
    assert "short-term" in md.lower() and "long-term" in md.lower()
    # the extraction-latency lesson must be present so the demo stays reliable
    assert "extraction" in md.lower()


def test_reuse_is_explained(nb):
    md = "\n".join(c.source for c in nb.cells if c.cell_type == "markdown")
    assert "build_agent_options" in md
    assert "one source of truth" in md.lower() or "source of truth" in md.lower()


def test_ab_contrast_is_taught(nb):
    """The honest A/B (memory on vs off on the SAME deployment) must appear."""
    text = "\n".join(c.source for c in nb.cells)
    assert '"memory": false' in text or "'memory': false" in text or "memory=false" in text.lower()
