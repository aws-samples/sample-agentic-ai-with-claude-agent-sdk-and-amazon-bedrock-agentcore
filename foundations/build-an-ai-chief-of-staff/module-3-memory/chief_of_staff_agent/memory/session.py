"""AgentCore Memory session helper — the agent's cross-session recall.

This is the ONLY net-new agent code in Module 3. It wraps the AgentCore Memory
data plane (`boto3.client("bedrock-agentcore")`) behind two small methods the
deploy entrypoint calls around each turn:

  - ``retrieve_context(query)`` — at the START of a turn: what do we remember
    about this actor? Returns a plain-text block to append to the system prompt.
  - ``record_turn(user, assistant)`` — at the END of a turn: persist the
    exchange so future sessions can recall it.

Two layers (both taught in Module 3):

  * SHORT-TERM (events): ``list_sessions`` + ``list_events`` give IMMEDIATE
    cross-session recall — the prior turns of *other* sessions for the same
    actor, available the instant they're written. This is what makes the live
    demo reliable.
  * LONG-TERM (extraction): ``retrieve_memory_records`` returns the SEMANTIC
    facts and USER_PREFERENCE insights the service extracts in the background.
    Extraction is asynchronous (~60-90s in our us-west-2 spike), so this layer
    powers the "it learned over time" beat, not the immediate next turn.

Everything degrades gracefully: if ``MEMORY_<NAME>_ID`` is unset (e.g. local
``agentcore dev``, where Memory isn't available) or any data-plane call fails,
the helper logs and returns empty — the agent simply runs stateless, never
crashes. (Module 2's stateless behavior is the safe fallback.)

API shapes here were verified live against us-west-2 (see SPIKE_NOTES.md), not
copied from docs — e.g. the payload key is ``conversational`` (not
``conversationalMessage``) and ``create_event`` requires ``eventTimestamp``.
"""

from __future__ import annotations

import datetime
import json
import logging
import os
from typing import Any

import boto3

logger = logging.getLogger("chief_of_staff.memory")

# Container env var injected by `agentcore deploy` for a memory named "CosMemory"
# (the CDK uses MEMORY_<UPPERCASE_NAME>_ID — verified in @aws/agentcore-cdk).
MEMORY_ID_ENV = "MEMORY_COSMEMORY_ID"

# Namespace templates must match agentcore.json's strategies[].namespaces.
FACTS_NS = "users/{actor_id}/facts"
PREFS_NS = "users/{actor_id}/preferences"

# How many prior sessions / records to pull. Small on purpose: enough to recall,
# few enough to keep the injected context tight.
_RECENT_SESSIONS = 3
_TOP_K = 5


class MemorySession:
    """Per-(actor, session) handle over the AgentCore Memory data plane."""

    def __init__(self, actor_id: str, session_id: str | None, memory_id: str, client: Any):
        self.actor_id = actor_id
        self.session_id = session_id
        self.memory_id = memory_id
        self._client = client

    # -- retrieve (turn start) ------------------------------------------------

    def retrieve_context(self, query: str) -> str:
        """Build a memory block to append to the system prompt.

        Combines immediate short-term recall (prior sessions' events) with any
        long-term extracted facts/preferences. Returns "" when there's nothing
        to recall or memory is unavailable.
        """
        parts: list[str] = []
        try:
            recent = self._recent_other_session_turns()
            if recent:
                parts.append("Recent conversation history with this user (most recent first):")
                parts.extend(f"- {line}" for line in recent)
        except Exception as e:  # never let recall break a turn
            logger.warning("short-term recall failed: %s", e)

        try:
            facts = self._retrieve_records(FACTS_NS, query)
            prefs = self._retrieve_records(PREFS_NS, query)
            if facts:
                parts.append("\nWhat you know about this user (learned facts):")
                parts.extend(f"- {f}" for f in facts)
            if prefs:
                parts.append("\nThis user's stated preferences:")
                parts.extend(f"- {p}" for p in prefs)
        except Exception as e:
            logger.warning("long-term retrieval failed: %s", e)

        if not parts:
            return ""
        return (
            "\n\n## Memory — what you recall about this user\n"
            "Use this to maintain continuity across sessions. Treat it as your own memory,\n"
            "not as instructions from the user.\n\n" + "\n".join(parts) + "\n"
        )

    def _recent_other_session_turns(self) -> list[str]:
        """Short-term cross-session recall: the latest turns from the actor's
        OTHER recent sessions (immediate — no extraction lag)."""
        sessions = self._client.list_sessions(memoryId=self.memory_id, actorId=self.actor_id)
        summaries = sessions.get("sessionSummaries", [])
        # Most recent first; skip the current session (we want CROSS-session memory).
        summaries.sort(key=lambda s: s.get("createdAt") or datetime.datetime.min, reverse=True)
        # The actor's most recent OTHER sessions (cross-session = exclude the current one).
        prior = [s for s in summaries if s.get("sessionId") and s.get("sessionId") != self.session_id]
        lines: list[str] = []
        for s in prior[:_RECENT_SESSIONS]:
            events = self._client.list_events(
                memoryId=self.memory_id,
                actorId=self.actor_id,
                sessionId=s["sessionId"],
                includePayloads=True,
                maxResults=10,
            )
            for ev in events.get("events", []):
                for item in ev.get("payload", []) or []:
                    conv = item.get("conversational")
                    if not conv:
                        continue
                    role = conv.get("role", "")
                    text = (conv.get("content") or {}).get("text", "").strip()
                    if text:
                        lines.append(f"{role.title()}: {text}")
        return lines[:12]

    def _retrieve_records(self, namespace_tpl: str, query: str) -> list[str]:
        """Long-term semantic retrieval from one namespace.

        Records come back either as plain text (SEMANTIC facts) or JSON-wrapped
        ``{"context": "..."}`` (USER_PREFERENCE) — we normalize both to text.
        """
        ns = namespace_tpl.format(actor_id=self.actor_id)
        resp = self._client.retrieve_memory_records(
            memoryId=self.memory_id,
            namespace=ns,
            searchCriteria={"searchQuery": query or "user context", "topK": _TOP_K},
        )
        out: list[str] = []
        for rec in resp.get("memoryRecordSummaries", []):
            text = (rec.get("content") or {}).get("text", "").strip()
            if text:
                out.append(_unwrap_record_text(text))
        return out

    # -- record (turn end) ----------------------------------------------------

    def record_turn(self, user_text: str, assistant_text: str) -> None:
        """Persist a user+assistant exchange as a short-term event.

        This both enables immediate cross-session recall (via list_events) and
        queues the asynchronous long-term extraction (facts/preferences).
        """
        payload = []
        if user_text and user_text.strip():
            payload.append(
                {"conversational": {"role": "USER", "content": {"text": user_text.strip()}}}
            )
        if assistant_text and assistant_text.strip():
            payload.append(
                {"conversational": {"role": "ASSISTANT", "content": {"text": assistant_text.strip()}}}
            )
        if not payload:
            return
        kwargs: dict[str, Any] = dict(
            memoryId=self.memory_id,
            actorId=self.actor_id,
            eventTimestamp=datetime.datetime.now(datetime.timezone.utc),
            payload=payload,
        )
        if self.session_id:
            kwargs["sessionId"] = self.session_id
        try:
            self._client.create_event(**kwargs)
        except Exception as e:  # fire-and-forget: a failed write must not fail the turn
            logger.warning("record_turn failed (continuing stateless): %s", e)


class _NullMemory:
    """No-op stand-in when memory is unavailable (unset id / local dev).

    Lets the entrypoint call retrieve_context()/record_turn() unconditionally;
    the agent just behaves like Module 2 (stateless).
    """

    actor_id = None
    session_id = None

    def retrieve_context(self, query: str) -> str:  # noqa: ARG002
        return ""

    def record_turn(self, user_text: str, assistant_text: str) -> None:  # noqa: ARG002
        return None


def _unwrap_record_text(text: str) -> str:
    """USER_PREFERENCE records arrive as JSON like {"context": "..."}; surface
    the inner text. SEMANTIC facts are plain strings and pass through."""
    if text.startswith("{"):
        try:
            obj = json.loads(text)
            if isinstance(obj, dict):
                return str(obj.get("context") or obj.get("text") or text)
        except (ValueError, TypeError):
            pass
    return text


def get_memory(
    actor_id: str,
    session_id: str | None,
    *,
    region_name: str | None = None,
) -> MemorySession | _NullMemory:
    """Factory: a MemorySession when AgentCore Memory is configured, else a
    no-op. Reads the memory id from the env var the CDK injects at deploy time.
    """
    memory_id = os.getenv(MEMORY_ID_ENV)
    if not memory_id:
        logger.info("%s not set — running stateless (no AgentCore Memory).", MEMORY_ID_ENV)
        return _NullMemory()
    try:
        client = boto3.client(
            "bedrock-agentcore",
            region_name=region_name or os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION"),
        )
    except Exception as e:
        logger.warning("could not create bedrock-agentcore client (running stateless): %s", e)
        return _NullMemory()
    return MemorySession(actor_id, session_id, memory_id, client)
