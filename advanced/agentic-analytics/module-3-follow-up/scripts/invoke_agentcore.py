#!/usr/bin/env python3
"""Multi-round clarification driver for the deployed Agentic Analytics agent.

The agent may ask follow-up questions (AskUserQuestion) before answering. AgentCore
is serverless and can't block for input, so the deployed entrypoint emits the
questions as a `clarification_needed` JSON block and returns. This terminal driver
closes that loop:

    invoke → detect clarification → collect answers → re-invoke (resume) → repeat
    until the agent answers (no more questions).

Usage:
    python scripts/invoke_agentcore.py "Show me the top students"
    python scripts/invoke_agentcore.py --runtime analytics "How are scholarships doing?"
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import uuid


def _extract_json_blocks(output: str) -> list[dict]:
    """Pull ```json ... ``` blocks out of the CLI output."""
    blocks = []
    for m in re.findall(r"```json\s*(\{.*?\})\s*```", output, re.DOTALL):
        try:
            blocks.append(json.loads(m))
        except json.JSONDecodeError:
            pass
    return blocks


def _find_clarification(output: str) -> dict | None:
    for b in _extract_json_blocks(output):
        if b.get("status") == "clarification_needed":
            return b
    return None


def _find_session_id(output: str) -> str | None:
    for b in _extract_json_blocks(output):
        if b.get("claude_agent_sdk_session_id"):
            return b["claude_agent_sdk_session_id"]
    m = re.search(r"Claude Agent SDK Session ID:\s*(\S+)", output)
    return m.group(1) if m else None


def _collect_answers(questions: list[dict]) -> str:
    """Show each question's options, collect the user's choice(s), return a prompt."""
    print("\n" + "─" * 70)
    print("The agent needs clarification:")
    lines = []
    for q in questions:
        print(f"\n{q.get('header', '')}: {q.get('question', '')}")
        options = q.get("options", [])
        for i, opt in enumerate(options, 1):
            print(f"  {i}. {opt.get('label', '')} — {opt.get('description', '')}")
        raw = input("Your choice (number, comma-separated, or free text): ").strip()
        try:
            picked = [options[int(x) - 1]["label"] for x in raw.split(",")]
            answer = ", ".join(picked)
        except (ValueError, IndexError):
            answer = raw
        lines.append(f"{q.get('question', '')} → {answer}")
    print("─" * 70)
    return "My answers:\n" + "\n".join(lines)


def _invoke(prompt: str, session_id: str, runtime: str | None,
            sdk_session_id: str | None) -> str:
    payload: dict = {"prompt": prompt}
    if sdk_session_id:
        payload["claude_agent_sdk_session_id"] = sdk_session_id
    cmd = ["agentcore", "invoke", json.dumps(payload), "--session-id", session_id]
    if runtime:
        cmd += ["--runtime", runtime]
    print(f"\n▶ invoking{' (resume)' if sdk_session_id else ''}…")
    proc = subprocess.run(cmd, capture_output=True, text=True)
    out = proc.stdout + proc.stderr
    print(out)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Multi-round clarification driver.")
    ap.add_argument("prompt", help="Your question for the agent")
    ap.add_argument("--runtime", default="analytics", help="runtime name (default: analytics)")
    ap.add_argument("--max-rounds", type=int, default=5)
    args = ap.parse_args()

    session_id = f"agentic-analytics-clarify-{uuid.uuid4().hex}"  # ≥33 chars
    prompt, sdk_session_id = args.prompt, None

    for _ in range(args.max_rounds):
        out = _invoke(prompt, session_id, args.runtime, sdk_session_id)
        sdk_session_id = _find_session_id(out) or sdk_session_id
        clar = _find_clarification(out)
        if not clar:
            print("\n✅ Done — the agent answered.")
            return 0
        prompt = _collect_answers(clar.get("questions", []))

    print("\n⚠️ Reached max rounds without a final answer.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
