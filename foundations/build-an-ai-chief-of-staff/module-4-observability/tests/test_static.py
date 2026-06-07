"""FAST — notebook hygiene for module-4-observability.ipynb."""
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
    for c in nb.cells:
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


def test_teaches_observability_flow(nb):
    md = "\n".join(c.source for c in nb.cells if c.cell_type == "markdown")
    for needle in ["Transaction Search", "GenAI", "session id", "opentelemetry-instrument",
                   "gen_ai.", "Cleanup"]:
        assert needle.lower() in md.lower(), f"notebook should mention {needle!r}"


def test_teaches_the_runtime_tracing_toggle(nb):
    """The per-runtime Tracing toggle is required for delivery — the notebook must teach it explicitly."""
    md = "\n".join(c.source for c in nb.cells if c.cell_type == "markdown")
    assert "Tracing" in md and "toggle" in md.lower()
    assert "emit" in md.lower() and "deliver" in md.lower(), (
        "notebook should distinguish emitting spans (container) from delivering them (runtime toggle)"
    )


def test_no_manual_spans_taught(nb):
    """Module 4 teaches reading auto-emitted spans, not hand-building them."""
    allsrc = "\n".join(c.source for c in nb.cells)
    assert "start_as_current_span" not in allsrc
    assert "BedrockInstrumentor" not in allsrc


def test_runnable_verification_present(nb):
    """The notebook includes a programmatic /aws/spans peek (not only 'go click the console')."""
    code = "\n".join(c.source for c in nb.cells if c.cell_type == "code")
    assert "aws/spans" in code
    assert "enable_transaction_search.py" in code
