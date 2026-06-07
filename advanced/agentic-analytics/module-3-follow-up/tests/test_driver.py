"""FAST — unit-test the clarification driver's parsing (no AWS, no subprocess)."""
from __future__ import annotations

import sys

from conftest import SCRIPTS_DIR

sys.path.insert(0, str(SCRIPTS_DIR))

import invoke_agentcore as drv  # noqa: E402

CLARIFY_OUTPUT = """
Some streamed text...
```json
{
  "request_id": "abc",
  "claude_agent_sdk_session_id": "sdk-sess-123",
  "status": "clarification_needed",
  "questions": [
    {"header": "Scope", "question": "Which semester?",
     "options": [{"label": "Fall 2025", "description": "current"},
                 {"label": "All time", "description": "every record"}]}
  ]
}
```
"""

ANSWER_OUTPUT = """
The answer is 1,234 students.
```json
{"request_id": "abc", "claude_agent_sdk_session_id": "sdk-sess-123",
 "generated_files": [], "note": "done"}
```
"""


def test_detects_clarification():
    clar = drv._find_clarification(CLARIFY_OUTPUT)
    assert clar is not None
    assert clar["questions"][0]["header"] == "Scope"


def test_no_clarification_on_final_answer():
    assert drv._find_clarification(ANSWER_OUTPUT) is None


def test_extracts_session_id_for_resume():
    assert drv._find_session_id(CLARIFY_OUTPUT) == "sdk-sess-123"
    assert drv._find_session_id(ANSWER_OUTPUT) == "sdk-sess-123"


def test_session_id_from_plain_text_fallback():
    assert drv._find_session_id("Claude Agent SDK Session ID: plain-abc\n") == "plain-abc"
