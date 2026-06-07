"""FAST static checks — notebook hygiene + agent config/skill/hook wiring. No model calls, no creds."""
from __future__ import annotations

import ast
import json
import re
from pathlib import Path

import nbformat
import pytest

from conftest import AGENT_DIR, CLAUDE_DIR, MODULE_DIR, NOTEBOOK, code_cells


@pytest.fixture(scope="module")
def nb():
    return nbformat.read(NOTEBOOK, as_version=4)


@pytest.fixture(scope="module")
def all_code(nb) -> str:
    return "\n\n".join(c.source for c in code_cells(nb))


@pytest.fixture(scope="module")
def all_markdown(nb) -> str:
    return "\n\n".join(c.source for c in nb.cells if c.cell_type == "markdown")


# ──────────────────────────────────────────── notebook structure / hygiene
def test_notebook_is_valid(nb):
    nbformat.validate(nb)


def test_every_code_cell_parses(nb):
    """Each code cell is syntactically valid Python (top-level await allowed)."""
    for i, cell in enumerate(code_cells(nb)):
        # Skip IPython line magics / shell escapes (e.g. `!bash setup.sh`, `%cd`) —
        # they're valid in a notebook kernel but not parseable as Python.
        lines = [ln for ln in cell.source.splitlines() if not ln.lstrip().startswith(("!", "%"))]
        wrapped = "async def _ph():\n" + "\n".join("    " + ln for ln in lines)
        try:
            ast.parse(wrapped)
        except SyntaxError:
            ast.parse("\n".join(lines))  # cells without await — re-raises with a clear message


def test_no_hardcoded_cookbook_model(all_code):
    """Bedrock-driven: the model comes from env, never a hardcoded Anthropic-API id."""
    assert "claude-opus-4-6" not in all_code


def test_uses_bedrock_provider(all_code):
    assert 'CLAUDE_CODE_USE_BEDROCK' in all_code


def test_skill_cell_enables_skill_tool(nb):
    """At least one cell wires the Skill tool together with project setting_sources."""
    skill_cells = [
        c.source for c in code_cells(nb)
        if '"Skill"' in c.source and "allowed_tools" in c.source
    ]
    assert skill_cells, "no cell enables the Skill tool"
    assert any('setting_sources=["project"]' in s for s in skill_cells)


def test_setting_sources_present_for_filesystem_features(nb):
    """Cells that rely on CLAUDE.md/skills/subagents/commands must load project settings."""
    for c in code_cells(nb):
        src = c.source
        needs_project = any(tok in src for tok in ('"Skill"', '"Task"', "outputStyle", "/budget-impact"))
        if needs_project and "ClaudeAgentOptions" in src:
            assert 'setting_sources=["project"]' in src, (
                f"cell uses a project feature but omits setting_sources=['project']:\n{src[:200]}"
            )


def test_teaching_content_present(all_markdown):
    """The scenario/architecture narrative and the query-vs-client comparison survived edits."""
    assert "The scenario: a Chief of Staff" in all_markdown
    # Architecture is shown as a rendered PNG (renders in Code Editor / JupyterLab / GitHub alike;
    # raw ```mermaid only renders in some viewers).
    assert "images/architecture.png" in all_markdown
    assert "`query()` vs. `ClaudeSDKClient`" in all_markdown
    assert "Interrupts" in all_markdown  # a distinctive row from the comparison table


# ──────────────────────────────────────────── regression: the cell-29 audit-read bug
def test_audit_read_cell_handles_dict_not_list(nb):
    """The audit log is a dict {"script_executions": [...]}. The reading cell must not
    index the top-level object as a list (the original `entries[-1]` bug -> KeyError)."""
    audit_cells = [c.source for c in code_cells(nb) if "script_usage_log.json" in c.source and "json.loads" in c.source]
    assert audit_cells, "audit-reading cell not found"
    src = audit_cells[0]
    assert 'script_executions' in src, "cell must read the 'script_executions' key"
    # must not do `entries = json.loads(...)` followed by `entries[-1]`
    assert not re.search(r"entries\s*=\s*json\.loads", src), "cell still treats the file as a bare list"


# ──────────────────────────────────────────── agent config
def test_settings_json_valid_and_hook_paths_exist():
    settings = CLAUDE_DIR / "settings.json"
    assert settings.exists(), "settings.json missing (must ship via setting_sources=project)"
    cfg = json.loads(settings.read_text())
    for group in cfg["hooks"]["PostToolUse"]:
        for hook in group["hooks"]:
            rel = hook["command"].replace("$CLAUDE_PROJECT_DIR/", "")
            assert (AGENT_DIR / rel).exists(), f"hook target missing: {rel}"


def test_no_stale_local_settings():
    """We renamed settings.local.json -> settings.json; the .local variant must be gone."""
    assert not (CLAUDE_DIR / "settings.local.json").exists()


def test_agent_module_imports_and_signature():
    """agent.py imports, exposes send_query(prompt, continue_conversation=...), no hardcoded model."""
    import sys

    sys.path.insert(0, str(MODULE_DIR))
    from chief_of_staff_agent.agent import send_query  # noqa: E402
    import inspect

    params = inspect.signature(send_query).parameters
    assert "prompt" in params
    assert "continue_conversation" in params

    src = Path(AGENT_DIR / "agent.py").read_text()
    assert "claude-opus-4-6" not in src
    assert 'setting_sources=["project"]' in src


def test_env_example_defines_bedrock_vars():
    env = (MODULE_DIR / ".env.example").read_text()
    for var in ("CLAUDE_CODE_USE_BEDROCK", "ANTHROPIC_MODEL", "AWS_REGION"):
        assert var in env


# ──────────────────────────────────────────── skill / subagent / command / output-style frontmatter
_FRONTMATTER = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)


def _md_files_with_frontmatter() -> list[Path]:
    roots = [
        CLAUDE_DIR / "skills",
        CLAUDE_DIR / "agents",
        CLAUDE_DIR / "commands",
        CLAUDE_DIR / "output-styles",
    ]
    files: list[Path] = []
    for r in roots:
        files.extend(r.rglob("*.md"))
    return files


@pytest.mark.parametrize("md", _md_files_with_frontmatter(), ids=lambda p: str(p.relative_to(AGENT_DIR)))
def test_markdown_assets_have_valid_frontmatter(md: Path):
    text = md.read_text()
    m = _FRONTMATTER.match(text)
    assert m, f"{md} missing YAML frontmatter"
    fm = m.group(1)
    assert re.search(r"^name:\s*\S+", fm, re.M), f"{md} frontmatter missing name"
    assert re.search(r"^description:\s*\S+", fm, re.M), f"{md} frontmatter missing description"


def test_financial_analysis_skill_exists():
    skill = CLAUDE_DIR / "skills" / "financial-analysis" / "SKILL.md"
    assert skill.exists()
    fm = _FRONTMATTER.match(skill.read_text()).group(1)
    assert "financial-analysis" in fm
