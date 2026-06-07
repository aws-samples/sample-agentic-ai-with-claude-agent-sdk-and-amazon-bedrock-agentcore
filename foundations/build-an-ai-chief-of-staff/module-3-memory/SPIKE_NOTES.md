# Module 3 — Phase 0 Spike Notes (us-west-2, verified)

These are the empirical findings that the "verify-live-first" spike resolved before the
notebook/demo was finalized. They override doc/pseudocode assumptions where they differ.

## 1. IAM is auto-wired by `agentcore deploy` (no manual policy needed)
Verified by reading the installed `@aws/agentcore-cdk` source:
- `dist/cdk/constructs/l3/AgentCoreApplication.js` → `wireMemoriesToAgents()` calls
  `memory.grant(runtime)` for every memory × every runtime, and
  `runtime.addEnvironmentVariable(memory.getEnvVarName(), memory.getEnvVarValue())`.
- `dist/cdk/constructs/components/primitives/memory/AgentCoreMemory.js`:
  - `grant()` attaches READ (`GetEvent/GetMemory/GetMemoryRecord/ListActors/ListEvents/ListSessions`),
    WRITE (`CreateEvent/DeleteEvent/DeleteMemoryRecord`), and namespace-scoped
    (`ListMemoryRecords/RetrieveMemoryRecords`) actions, resource = the memory ARN.
  - `getEnvVarName()` → `` `MEMORY_${name.toUpperCase()}_ID` `` → for `name:"CosMemory"` the
    container env var is **`MEMORY_COSMEMORY_ID`** (value = the memory id).
- ⇒ No explicit CDK policy addition required for Module 3.

## 2. LTM extraction latency — MEASURED (the gating demo fact)
Standalone memory (SEMANTIC `users/{actorId}/facts` + USER_PREFERENCE
`users/{actorId}/preferences`), one rich event, polled `retrieve_memory_records`:
- Memory `CREATING → ACTIVE`: **~150s**.
- After event write: **USER_PREFERENCE populated ~64s**, **SEMANTIC populated ~80s**.
- ⇒ LTM is NOT available for an immediate next-turn live demo. **Cross-session recall in the
  live demo MUST ride on short-term `list_events` (immediate).** LTM is the "learned over
  time / after a gap" inspect beat.
- Extraction quality was excellent and matched the demo narrative:
  - facts: `"The user is modeling a Series B fundraise with a $42.5M target and an 18-month bridge."`
  - prefs: `"The user prefers runway to always be reported in weeks, not months."`
- NOTE: preference records come back **JSON-wrapped** (`{"context":"..."}`); fact records come
  back as **plain text**. `retrieve_context()` must tolerate both.

## 3. boto3 data-plane shapes — VERIFIED via botocore introspection (botocore 1.43.22)
Corrects the memory-guide pseudocode:
- **`create_event`** required = `memoryId, actorId, eventTimestamp, payload`.
  - `payload[]` item key is **`conversational`** (NOT `conversationalMessage`).
  - `conversational` = `{ "role": <USER|ASSISTANT|TOOL|OTHER>, "content": {"text": str} }`
    — `content` is a **struct**, not a list; `role`+`content` required.
  - `eventTimestamp` is **required** (a datetime).
  - `sessionId` is optional on create_event but **required** on `list_events`/`get_event`.
- **`retrieve_memory_records`** required = `memoryId, searchCriteria`; `namespace` is a
  **top-level** param. `searchCriteria = {"searchQuery": str, "topK"?: int}`.
  - Output: `memoryRecordSummaries[].{ memoryRecordId, content:{text}, memoryStrategyId,
    namespaces[], createdAt, score? }`.
- **`list_events`** required = `memoryId, sessionId, actorId`; pass `includePayloads=True`.
- **`list_sessions`** required = `memoryId, actorId`; output `sessionSummaries[].{sessionId,
  actorId, createdAt}` → sort by `createdAt` desc to find an actor's recent prior sessions.
- **`list_actors`** → `actorSummaries[].actorId`.

## 4. agentcore.json memory schema (installed @aws/agentcore-cdk zod)
- `eventExpiryDuration`: integer **min 7, max 365** (CLI `add memory --expiry` default 30).
- `strategies[].type` ∈ `SEMANTIC | SUMMARIZATION | USER_PREFERENCE | EPISODIC`.
- `namespaces` support `{actorId}`, `{sessionId}`, `{memoryStrategyId}`; CFN now prefers
  `namespaceTemplates` (the construct falls back from `namespaceTemplates` → `namespaces`).
- CLI: `agentcore add memory --name --strategies SEMANTIC,USER_PREFERENCE --expiry 7`;
  `agentcore remove memory --name`; `agentcore status --type memory`.

## 5. Operational
- **Memory is NOT available during `agentcore dev`** (memory guide). Flow = deploy → invoke
  (cloud) → observe. Local dev mocks/skips memory.
- Region trap: this shell defaults to `AWS_REGION=ap-southeast-2`; the workshop target is
  **us-west-2** (from `aws-targets.json`). Pin region explicitly.
- Account/region live in `agentcore/aws-targets.json` (gitignored); commit only the example.
