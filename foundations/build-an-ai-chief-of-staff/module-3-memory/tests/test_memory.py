"""FAST — the memory helper's logic, with NO AWS calls.

Two things matter here and are easy to break by accident:
  1. Graceful degradation: no MEMORY_COSMEMORY_ID (e.g. local `agentcore dev`) → a no-op
     memory, so the agent runs stateless instead of crashing.
  2. The data-plane SHAPES match what the live service expects (verified in SPIKE_NOTES.md):
     create_event uses the `conversational` key with content {"text": ...} and an
     eventTimestamp; retrieve passes a top-level namespace + searchCriteria; cross-session
     recall uses list_sessions → list_events and EXCLUDES the current session.

We inject a fake boto3 client so these run offline and deterministically.
"""
from __future__ import annotations

import sys

import pytest

from conftest import AGENT_DIR

sys.path.insert(0, str(AGENT_DIR))

from memory.session import MemorySession, _unwrap_record_text, get_memory  # noqa: E402


class FakeMemoryClient:
    """Records calls and returns canned AgentCore Memory responses (verified shapes)."""

    def __init__(self):
        self.events = []
        self.retrieve_calls = []

    def create_event(self, **kwargs):
        self.events.append(kwargs)
        return {"event": {"eventId": "evt-1", **kwargs}}

    def list_sessions(self, **kwargs):
        # Two prior sessions for this actor (most recent last to test sorting).
        return {"sessionSummaries": [
            {"sessionId": "sess-old", "actorId": kwargs["actorId"], "createdAt": 1},
            {"sessionId": "sess-recent", "actorId": kwargs["actorId"], "createdAt": 2},
        ]}

    def list_events(self, **kwargs):
        return {"events": [
            {"payload": [
                {"conversational": {"role": "USER", "content": {"text": f"hi from {kwargs['sessionId']}"}}},
                {"conversational": {"role": "ASSISTANT", "content": {"text": "ack"}}},
            ]}
        ]}

    def retrieve_memory_records(self, **kwargs):
        self.retrieve_calls.append(kwargs)
        if "facts" in kwargs["namespace"]:
            return {"memoryRecordSummaries": [
                {"content": {"text": "Series B target is $42.5M with an 18-month bridge."}},
            ]}
        return {"memoryRecordSummaries": [
            {"content": {"text": '{"context": "prefers runway reported in weeks, not months"}'}},
        ]}


def _session(client, actor="techstart-cos", session_id="sess-current"):
    return MemorySession(actor, session_id, "CosMemory-abc", client)


def test_get_memory_degrades_when_unset(monkeypatch):
    monkeypatch.delenv("MEMORY_COSMEMORY_ID", raising=False)
    mem = get_memory("techstart-cos", "sess-1")
    assert type(mem).__name__ == "_NullMemory"
    assert mem.retrieve_context("runway") == ""
    assert mem.record_turn("u", "a") is None  # no-op, no crash


def test_record_turn_uses_verified_payload_shape():
    client = FakeMemoryClient()
    _session(client).record_turn("What's our runway?", "About 20 months.")
    assert len(client.events) == 1
    ev = client.events[0]
    assert ev["memoryId"] == "CosMemory-abc"
    assert ev["actorId"] == "techstart-cos"
    assert ev["sessionId"] == "sess-current"
    assert "eventTimestamp" in ev                       # required by the API
    roles = [p["conversational"]["role"] for p in ev["payload"]]
    assert roles == ["USER", "ASSISTANT"]               # uppercase enum
    # content is a struct {"text": ...}, not a list
    assert ev["payload"][0]["conversational"]["content"] == {"text": "What's our runway?"}


def test_record_turn_skips_empty():
    client = FakeMemoryClient()
    _session(client).record_turn("", "")
    assert client.events == []


def test_record_turn_swallows_errors():
    class Boom(FakeMemoryClient):
        def create_event(self, **kwargs):
            raise RuntimeError("AccessDenied")

    # must not raise — a failed write degrades to stateless
    _session(Boom()).record_turn("u", "a")


def test_retrieve_context_combines_layers_and_excludes_current_session():
    client = FakeMemoryClient()
    block = _session(client).retrieve_context("what did we decide on the raise?")
    # short-term recall pulled from prior sessions, NOT the current one
    assert "sess-current" not in block
    assert "hi from sess-recent" in block and "hi from sess-old" in block
    # long-term facts + (json-unwrapped) preferences both surfaced
    assert "$42.5M" in block
    assert "prefers runway reported in weeks" in block
    # retrieval was scoped to the actor's namespaces
    namespaces = {c["namespace"] for c in client.retrieve_calls}
    assert "users/techstart-cos/facts" in namespaces
    assert "users/techstart-cos/preferences" in namespaces
    # searchCriteria shape
    assert all("searchQuery" in c["searchCriteria"] for c in client.retrieve_calls)


def test_retrieve_context_empty_when_nothing_recalled():
    class Empty(FakeMemoryClient):
        def list_sessions(self, **kwargs):
            return {"sessionSummaries": []}

        def retrieve_memory_records(self, **kwargs):
            return {"memoryRecordSummaries": []}

    assert _session(Empty()).retrieve_context("anything") == ""


@pytest.mark.parametrize("raw,expected", [
    ("plain fact text", "plain fact text"),
    ('{"context": "wrapped pref"}', "wrapped pref"),
    ('{"text": "alt key"}', "alt key"),
    ("{not json", "{not json"),
])
def test_unwrap_record_text(raw, expected):
    assert _unwrap_record_text(raw) == expected
