# Project: Agentic AI with Claude Agent SDK + Amazon Bedrock AgentCore

> ⚠️ **ALWAYS clear notebook outputs before committing.** Notebook cell *outputs* must never be
> committed — they have leaked real AWS account ids, ARNs, and S3 presigned-URL temporary credentials
> (`ASIA…` access keys + `X-Amz-Security-Token`) from live runs. Before any commit that touches
> `*.ipynb`, run:
> ```bash
> jupyter nbconvert --clear-output --inplace path/to/*.ipynb   # or: uv run jupyter nbconvert ...
> ```
> Only commit notebook *source* (code + markdown), never run artifacts. (Participants generate their
> own outputs.) If you find committed outputs, scrub them by matching output CONTENT, not cell numbers.

This repo holds the **code** for a hands-on workshop. The **instructions** live in a separate
Workshop Studio repo (`democratizing-business-intelligence-by-using-claude-agent-sdk-on-amazon-bedrock-agentcore`),
which has already been refactored into the new "ladder" structure below. This repo is being rebuilt
to match it.

> This file is a **project record for developers / future sessions** — what the repo is and where we
> are. It is *not* an agent runtime file. The agent's own context lives at
> `foundations/build-an-ai-chief-of-staff/module-1-local-agent/chief_of_staff_agent/CLAUDE.md`
> (loaded by the SDK via `setting_sources`).

## The workshop = a progressive ladder (use-case-agnostic)

**Two top-level tracks** (each a self-contained use case):
- **`foundations/build-an-ai-chief-of-staff/`** — the core ladder, Modules 1–4 (Chief-of-Staff agent).
- **`advanced/agentic-analytics/`** — optional BI track, Modules 0–3 (text-to-SQL agent on Athena).

| Module | Teaches | Status in this repo |
|--------|---------|---------------------|
| **1 — Local agent** | `query()` one-liner → `ClaudeSDKClient` + system prompt + `CLAUDE.md` + skills + multi-turn | ✅ **Built & tested** |
| **2 — Deploy** | Wrap the agent in an AgentCore Runtime entrypoint, deploy (Container/ECR), invoke over HTTP | ✅ **Built & live-verified (us-west-2)** |
| **3 — Memory** | AgentCore Memory (short-term events + long-term extraction); single-tenant | ✅ **Built & live-verified (us-west-2): deploy + cross-session recall round-trip** |
| **4 — Observability** | View agent traces in AgentCore Observability / CloudWatch GenAI dashboard | ✅ **Built & live-verified (us-west-2)** |
| **Advanced (optional)** | `agentic-analytics/` — text-to-SQL BI agent on Athena (M0 setup → M1 local → M2 deploy+observe → M3 follow-up) | ✅ **Rebuilt & live-verified (us-west-2)** |

The running example for Modules 1–4 is the **Chief of Staff agent** (fictional startup "TechStart Inc" —
runway / burn / hiring analysis), adapted from the Claude cookbook. It needs **near-zero infra**: just
AWS credentials + Amazon Bedrock model access (no Athena/S3).

## Repo layout

```
.
├── foundations/build-an-ai-chief-of-staff/   # ✅ the Chief-of-Staff ladder (Modules 1–4)
│   ├── module-1-local-agent/          # ✅ Module 1 — self-contained, uv-managed
│   │   ├── module-1-local-agent.ipynb # single notebook: Part 1A → 1B → "all together"
│   │   ├── chief_of_staff_agent/      # the agent's body (read from disk by the SDK)
│   │   │   ├── agent.py               # send_query() entrypoint (Module 2 will deploy this)
│   │   │   ├── CLAUDE.md              # agent runtime context (NOT this file)
│   │   │   ├── .claude/{skills,agents,commands,hooks,output-styles,settings.json}
│   │   │   ├── scripts/  financial_data/  audit/  output_reports/
│   │   ├── utils/                     # HTML render helpers (from cookbook)
│   │   ├── tests/                     # pytest harness (fast + slow tiers) — see Testing
│   │   ├── setup.sh  pyproject.toml  .env.example
│   ├── module-2-deploy/                # ✅ Module 2 — deploy the SAME agent to AgentCore Runtime
│   │   ├── module-2-deploy.ipynb       # guided notebook: configure → dev → deploy → invoke → cleanup
│   │   ├── chief_of_staff_agent/       # COPY of Module 1's bundle + agent_agentcore.py (thin entrypoint)
│   │   │   ├── agent_agentcore.py      # @app.entrypoint — reuses build_agent_options() (no dup logic)
│   │   │   ├── Dockerfile              # Linux/arm64; pip-installs SDK fresh (CodeZip can't — see below)
│   │   │   └── pyproject.toml          # in-container deps (SDK + bedrock-agentcore + aws-otel-distro)
│   │   ├── agentcore/                  # @aws/agentcore project (agentcore.json, CDK, aws-targets.example.json)
│   │   ├── tests/                      # fast (reuse/config/static) + slow (live deploy) tiers
│   │   ├── setup.sh  pyproject.toml  .env.example
│   ├── module-3-memory/                # ✅ Module 3 — give the SAME agent cross-session memory (single-tenant)
│   │   ├── module-3-memory.ipynb        # guided: deploy → session A (state fact) → session B (recall) → A/B → inspect LTM → cleanup
│   │   ├── chief_of_staff_agent/        # M2 bundle + memory/session.py + memory-aware agent_agentcore.py
│   │   │   ├── memory/session.py        # get_memory(): retrieve_context() (STM list_events + LTM retrieve) + record_turn() (create_event)
│   │   │   └── agent_agentcore.py       # @app.entrypoint invoke(payload, context) — recall → run → record; {"memory":false} A/B toggle
│   │   ├── agentcore/                   # agentcore.json with memories[] (SEMANTIC facts + USER_PREFERENCE prefs)
│   │   ├── SPIKE_NOTES.md               # Phase-0 live findings (IAM auto-wired, LTM latency, verified boto3 shapes)
│   │   ├── tests/  setup.sh  pyproject.toml  .env.example
│   ├── module-4-observability/         # ✅ Module 4 — trace the deployed agent in CloudWatch
│   │   ├── module-4-observability.ipynb # guided: Transaction Search → deploy → invoke → view (no manual toggle; see M4 notes)
│   │   ├── chief_of_staff_agent/        # SAME bundle as M2; Dockerfile CMD wraps `opentelemetry-instrument`
│   │   ├── scripts/enable_transaction_search.py  # idempotent account-level setup
│   │   ├── agentcore/  tests/  setup.sh  pyproject.toml  .env.example
├── advanced/agentic-analytics/    # ✅ optional BI track — text-to-SQL agent on Athena (rebuilt, live-verified)
│   ├── module-0-setup/            # one-shot infra: scripts/setup_infrastructure.py (S3 + Athena DB/tables) + verify()
│   ├── module-1-local-agent/      # the BI agent local; analytics_agent/agent.py build_agent_options() (one source of truth)
│   ├── module-2-deploy/           # deploy + observability; full CLI lifecycle (create→deploy→invoke→traces); CDK injects Athena/S3/Glue IAM
│   ├── module-3-follow-up/        # AskUserQuestion clarification + serverless multi-round session resume
└── CLAUDE.md  LICENSE  CONTRIBUTING.md  CODE_OF_CONDUCT.md  .gitignore
```

## Conventions established

- **Bedrock, not the Anthropic API.** No hardcoded `model=` in agent code — the model comes from
  `ANTHROPIC_MODEL` + `CLAUDE_CODE_USE_BEDROCK=1` in `.env`. (Note: a pre-set shell `AWS_REGION` and the
  Claude Code CLI's own model config can override `.env`, since `load_dotenv()` doesn't override existing
  env vars.)
- **Each module is self-contained**, with its own `pyproject.toml` and local `.venv` (uv). There is no
  top-level Python project.
- **Dependencies are pinned exactly (`==`)**, not `>=` — runtime and test deps alike.
- **Skills vs. CLAUDE.md vs. subagents** are taught as three distinct mechanisms: procedure / always-on
  facts / task delegation.
- Setup steps (Node + AgentCore CLI, `npm ci`, `uv sync`, kernel install) live in a per-module
  **`setup.sh`** (the READMEs were removed; deeper setup prose lives in the Workshop Studio pages). Each
  notebook keeps an **equivalent setup cell** at the top as a fallback so it can bootstrap its own kernel.
- **Notebook command style is mixed by design** — both `!agentcore …` shell-escape cells and
  `subprocess.run([...])` cells appear, chosen for whatever reads clearest locally; there is **no
  mandate to unify them**. `agentcore dev` stays a **terminal** step (it's a long-running server that
  would block the kernel). The static test (`test_code_cells_parse`) skips lines starting with `!`/`%`
  before `ast.parse`, so both styles pass.

### Module 2 / deployment decisions (from a real AWS spike)
- **Tooling = the new `@aws/agentcore` npm CLI** (`agentcore create/add/deploy/invoke/remove`,
  config = `agentcore/agentcore.json`, CDK-based). The old `bedrock-agentcore-starter-toolkit` is
  **deprecated** — do not use it.
- **Build type = Container, NOT CodeZip.** The Claude Agent SDK bundles a ~218MB native CLI
  (`claude_agent_sdk/_bundled/claude`). With CodeZip the deploy *succeeds* but `invoke` fails:
  `Permission denied: .../_bundled/claude` (zip strips the execute bit). Container `pip install`s the SDK
  fresh on Linux/arm64 → correct arch + perms. (Proven both ways in the spike.)
- **Reuse = shared `build_agent_options()`** in `agent.py` (single source of truth). The deploy entrypoint
  `agent_agentcore.py` is thin: `@app.entrypoint` + payload parse + streaming, calling
  `build_agent_options()`. A test (`test_reuse.py`) guards against drift / duplicated logic.
- **Bundle reuse mechanism:** Module 2 holds a **copy** of Module 1's `chief_of_staff_agent/` (Container
  build needs all code under one `codeLocation`). A drift-guard test asserts the two `agent.py` are
  byte-identical. *(Open question for review: copy vs. a shared package — see morning summary.)*
- **Execution IAM role is auto-created by the CDK** (Bedrock invoke + CloudWatch Logs + X-Ray) — no manual
  role script needed.
- **`agentcore.json` natively supports `memories[]` (Module 3) and `instrumentation.enableOtel` (Module
  4)** — both are config additions, not rework.
- **Account ID hygiene:** `agentcore/aws-targets.json` (real 12-digit account) is **gitignored**; commit
  only `aws-targets.example.json`. Participants copy + fill it in.
### Module 4 / observability decisions (live-verified on us-west-2)
Observability adds **zero agent code** (same bundle as M2; drift-guard test enforces it). The archived
745-line manual `openinference`/hand-span approach is **obsolete** — not used.

**CORRECTED understanding (the earlier "three switches, all required" framing was overstated).** The
per-runtime **Tracing toggle is NOT a hard gate for the agent's own traces** — it controls a *different*
class of span. There are two span sources + one real gate:
1. **Account-level CloudWatch Transaction Search** — the ONE true hard gate. Nothing is searchable in
   `/aws/spans` without it. One-time per account; the `b41a20e` Phase-1 edit + this track rely on
   `agentcore deploy` auto-enabling it (or `scripts/enable_transaction_search.py`).
2. **Application spans (the agent's own GenAI/tool-call/token-usage spans the dashboard renders)** —
   emitted by the **container** via ADOT (`opentelemetry-instrument` CMD + `AGENT_OBSERVABILITY_ENABLED`
   + `OTEL_*` exporter env). This is the "enable observability in agent code" path: the in-container ADOT
   SDK exports straight to CloudWatch via OTLP, so these flow **whether or not the runtime Tracing toggle
   is on**. (BYO-Container with a custom CMD: the runtime does NOT auto-inject the wrapper, so we add it.)
3. **Per-runtime Tracing toggle** — a console action (AgentCore → Agent Runtime → agent → Tracing → Edit
   → Enable; no public CLI field). It only governs **service-generated runtime spans** (the platform-level
   `POST /invocations` resource span) — NOT the agent's application spans. So the dashboard shows the
   agent's traces even with the toggle "Not enabled". Phase-1 M4 dropped its manual-toggle step in
   `b41a20e remove the trace toggle` for this reason.
- **Why the old note was wrong:** the earlier "spike" watched specifically for the `POST /invocations`
  span (which IS service-generated and *does* need the toggle) and over-generalized to "without the
  toggle, spans never reach CloudWatch." Agent application spans never needed it.
- **Session ids must be ≥33 chars** for `agentcore invoke`.
- **Other gotcha:** pin `aws-cdk-lib` **exactly** in `agentcore/cdk/package.json` — a floating `^` let it
  resolve to a lib newer than the bundled `aws-cdk` CLI could read (CDK synth "schema version" error).
### Module 3 / memory decisions (Phase-0 spike-verified on us-west-2; see `module-3-memory/SPIKE_NOTES.md`)
Chosen approach = **AgentCore Memory** (over the Runtime persistent filesystem — verified per-session/
ephemeral, the opposite of the mandate — and over a DIY SessionStore/vector store — re-implements a
managed service). **Single-tenant** (one fixed `actor_id = "techstart-cos"`); multi-tenant is documented
as a follow-on, not built.
- **`agent.py` gained one additive param: `system_prompt_suffix`** (backported into Module 1 and re-synced
  to ALL bundle copies — the byte-identical drift-guard still passes). Memory is injected via
  `build_agent_options(system_prompt_suffix=recalled_text)`, NOT a forked `system_prompt=` — which also
  keeps `test_reuse.py`'s "no `system_prompt=` in the entrypoint" guard green. ⚠️ This means Module 1's
  `agent.py` is **no longer the same bytes as before this module** — all four copies changed together.
- **Entrypoint is now `invoke(payload, context)` (2 args).** The runtime only delivers the request context
  (→ `context.session_id`) when the 2nd param is literally named `context` (verified in
  `bedrock_agentcore/runtime/app.py::_takes_context`). `memory/session.py` is the only net-new agent code.
- **IAM is AUTO-WIRED — no manual policy.** `agentcore deploy` with a populated `memories[]` grants the
  runtime role the memory data-plane actions (CreateEvent/ListEvents/ListSessions/RetrieveMemoryRecords/…)
  and injects the env var **`MEMORY_<UPPERCASE_NAME>_ID`** (for `CosMemory` → `MEMORY_COSMEMORY_ID`).
  Verified by reading the installed `@aws/agentcore-cdk` (`AgentCoreApplication.wireMemoriesToAgents()` →
  `AgentCoreMemory.grant()`).
- **Two layers, and the latency gotcha that shapes the demo:** short-term events (`create_event`/
  `list_events`) are **immediate**; long-term extraction (SEMANTIC facts + USER_PREFERENCE) is
  **async** (measured: prefs ~64s, facts ~80s after a write; memory ~150s to `ACTIVE`). So **live
  cross-session recall rides on short-term `list_events`** of the actor's prior sessions; LTM is the
  "learned over time" inspect beat. `retrieve_context()` queries both.
- **Verified boto3 shapes (NOT the guide's pseudocode):** `create_event` payload key is **`conversational`**
  (not `conversationalMessage`), `content` is a struct `{"text": ...}`, `eventTimestamp` is **required**,
  role enum is **`USER`/`ASSISTANT`**. `retrieve_memory_records` takes a **top-level `namespace`** +
  `searchCriteria={"searchQuery","topK"}`. `list_events` **requires `sessionId`**; `list_sessions` returns
  `sessionSummaries[].{sessionId,actorId,createdAt}`. USER_PREFERENCE records come back JSON-wrapped
  (`{"context": "..."}`); SEMANTIC facts are plain text — `_unwrap_record_text` handles both.
- **`eventExpiryDuration` min is 7** (installed CDK zod), not the 3 the older guide text claims; we use 7.
- **Graceful degradation:** unset `MEMORY_COSMEMORY_ID` (e.g. local `agentcore dev`, where Memory is
  unavailable) or any data-plane error → `_NullMemory`, agent runs stateless (never crashes).
- **Demo honesty:** the recalled value (`$42.5M`) is **invented in-session** because the bundle's
  `CLAUDE.md` hardcodes a **$30M** Series B (line 40) — reusing $30M would prove nothing. Proof is a
  same-deployment **A/B** (`{"memory": false}`), not a comparison against the M2 deployment.
- **LIVE-VERIFIED (us-west-2):** the slow test (`test_deploy_live.py`) passed end-to-end in ~11 min —
  deploy provisioned runtime + CosMemory, session A wrote the `$42.5M` fact, **session B recalled it**
  (no AccessDenied → IAM auto-wiring confirmed live), then teardown destroyed both resources (0 memories /
  0 runtimes after) and restored the config snapshot.
- **CDK reproducibility gotcha (pre-existing, repo-wide):** `agentcore deploy` runs `npm run build` (`tsc`),
  which needs the CDK project's `node_modules` AND `lib/cdk-stack.ts`. BOTH are **gitignored**
  (`cdk/.gitignore` ignores `node_modules`; root `.gitignore:17` ignores `lib/`), so a fresh git checkout
  of any module's `agentcore/cdk/` can't deploy until you `npm ci` there and restore `lib/cdk-stack.ts`.
  M2/M4 only deploy because their copies exist locally from prior runs. For M3 I had to `npm ci` and copy
  `lib/cdk-stack.ts` from M2. **Flag for a repo-wide fix** (commit `lib/cdk-stack.ts`, or regenerate it +
  `npm ci` as a documented setup step). The deploy also fails fast with `sh: tsc: command not found` when
  `node_modules` is absent — a clear signal of this.

## Testing

Each module has its own `tests/` (run from inside the module folder). Assertions are
**structural/behavioral** (not exact text) to tolerate model non-determinism; the slow tier auto-skips
when prerequisites are missing.

```bash
# Module 1
uv run --group test pytest            # FAST: static + scripts + hooks (no creds)
uv run --group test pytest -m slow    # SLOW: executes the notebook on Bedrock (creds, ~15 min)

# Module 2
uv run --group test pytest            # FAST: reuse/drift-guard + config + Dockerfile + notebook (no creds/Docker)
uv run --group test pytest -m slow    # SLOW: real agentcore deploy+invoke round-trip (creds)

# Module 3
uv run --group test pytest            # FAST: reuse/drift-guard + suffix/context + memory-helper logic (fake client) + memories[] config + notebook
uv run --group test pytest -m slow    # SLOW: deploy → session A writes → session B recalls (STM) → assert no AccessDenied

# Module 4
uv run --group test pytest            # FAST: drift-guard + enableOtel/OTEL-wrapper config + TS helper + notebook
uv run --group test pytest -m slow    # SLOW: enable TS → deploy → invoke → assert OTEL active; span check best-effort

# Advanced track (advanced/agentic-analytics/<module>) — same FAST/SLOW split per module
# M0: FAST static (script parses, idempotency markers, no manual IAM, notebook) · SLOW reuses verify() on live S3/Athena
# M1: FAST options-shape/no-hardcoded-model/clarification-override/bundle/notebook · SLOW runs the agent on Bedrock+Athena
# M2: FAST reuse-drift-guard/config(enableOtel,Dockerfile,cdk-lib pinned)/notebook · SLOW real create→deploy→invoke→teardown
# M3: FAST reuse(clarification-via-builder,resume,clarification-json)/driver-unit/config · SLOW deploy + ask→answer+resume round-trip
```

Verified green: Module 1 fast 33 + slow 7 (live Bedrock); Module 2 **fast 16** + live deploy/invoke on
us-west-2; Module 3 **fast 31** (reuse 9 + config 7 + memory-helper 9 + notebook 6) + **slow 2 live-verified
on us-west-2** (deploy runtime+CosMemory → session A writes `$42.5M` → session B recalls it, no AccessDenied →
IAM auto-wiring confirmed → teardown destroyed both; ~11 min); Module 4 **fast 15** + **live-verified
end-to-end** on us-west-2 (the service `POST /invocations` span reached `/aws/spans` after enabling the
runtime Tracing toggle — but note that toggle is only needed for *that* service span; the agent's own
application spans flow without it, see the corrected Module 4 section).

> **Deploy note:** local Docker is NOT needed — the `@aws/agentcore` Container build runs in the cloud
> (CodeBuild, ARM64). `agentcore deploy` reads the target from `agentcore/aws-targets.json` (gitignored);
> the account/region must be CDK-bootstrapped first (`cdk bootstrap`).

### Advanced track — `advanced/agentic-analytics/` (rebuilt Phase 2; live-verified us-west-2)
Text-to-SQL BI agent over a fictional Student Analytics dataset on Athena. Replaces the old
`advanced/text-to-sql-athena/` (deleted). Four self-contained uv modules mirroring the Phase-1 ladder.
- **Decisions:** parent `agentic-analytics/`, inner `module-0..3`; CLI **`@aws/agentcore@0.17.0`** (same
  as Phase 1, NOT preview). **4 modules** (observability folded into M2). Agent bundle dir is
  `analytics_agent/`; one-source-of-truth = `analytics_agent/agent.py` `build_agent_options()` (drift-guard
  keeps M1/M2/M3 byte-identical). Clarification (M3) is an OVERRIDE flag `enable_clarification=True`, not a fork.
- **Observability collapses to config** — the 0.17.0 CLI ALREADY does it (verified by tarball diff + a live
  Phase-0 spike): `enableOtel:true` → the container template wraps `opentelemetry-instrument`, and
  `agentcore deploy` auto-enables account-level Transaction Search (the one real gate). The agent's own
  application spans (GenAI/tool/token) are exported by the in-container ADOT SDK and are reachable via
  `agentcore traces list` **without the per-runtime Tracing toggle** — that toggle only governs the
  service-generated `POST /invocations` span, not the agent's traces (see the corrected Module 4 section
  above for the full two-span-sources breakdown). So the old 745+539-line hand-rolled `*_observable.py`
  approach is **deleted**; a test guards against its return. (We keep the
  `openinference-instrumentation-claude-agent-sdk` dep for richer spans.)
- **M2 teaches the FULL CLI lifecycle** (not deploy-only): `agentcore create --no-agent` + `add agent
  --type byo` (scaffold) → configure → `deploy` → `invoke` → `traces`. A known-good `agentcore/` is committed
  as the fallback. `add agent` requires `--framework` even for BYO (no claude-agent-sdk option; we pass
  `Strands` — it's ignored for BYO + our own bundle/Dockerfile).
- **IAM:** the deployed runtime calls Athena/Glue/S3. The CDK auto-role only has Bedrock+Logs+X-Ray, so
  `cdk/lib/cdk-stack.ts` adds Athena/Glue/S3 statements via `application.environments → runtime.role
  .addToPrincipalPolicy(...)` — every deploy gets them, no manual step. (Confirmed live: the deployed role
  carried AthenaQueryExecution/GlueCatalogAccess/S3DataAndResults and the agent queried Athena + wrote S3.)
- **CDK floating-version trap (same class the repo already flagged):** a fresh `agentcore create` pins
  `aws-cdk-lib: ^2.248.0` → npm resolves 2.258.0 (cloud-assembly schema 54) but the bundled `aws-cdk` CLI
  (2.1100.1) reads only schema 53 → synth fails. **Fix: pin `aws-cdk-lib` EXACTLY (2.257.0)** in
  `cdk/package.json` + commit `package-lock.json` so `npm ci` reproduces it.
- **Module 0 infra script.** `scripts/setup_infrastructure.py` is idempotent (S3 bucket + upload 2 demo
  CSVs + `CREATE DATABASE/TABLE IF NOT EXISTS` + smoke query) and prints a human ✅ checklist via a
  `verify()` function that the SLOW test reuses. Table DDL uses Athena PHYSICAL types and lives in the
  script (NOT derived from the metadata YAML — that's the agent's LOGICAL schema, a different layer).
  **Run flow (changed in `phase2 beta`):** `setup.sh` now only installs deps + registers the kernel; the
  notebook's own cell runs `setup_infrastructure.py --region {REGION}` (participants see infra creation in
  the notebook, not hidden in setup.sh). Default region is now **auto-detected (falls back to us-east-1)**,
  not hardcoded us-west-2.
- **Data placement:** the 16MB demo CSVs live ONLY in `module-0-setup/data/` (setup-time → S3). The ~20KB
  metadata YAML + sample CSVs live in each agent bundle's `data/metadata/` (runtime schema docs).
- **`_default_output_location()` in agent.py** derives the Athena results bucket from the account id, so
  nothing account-specific is hardcoded in committed config (M2 entrypoint reuses it). ⚠️ It calls STS, so
  the Athena executor is built **lazily on first tool use** (not when `build_agent_options()` runs) — that
  keeps `build_agent_options()` a pure, no-AWS call the FAST tests can exercise without credentials. (A
  `phase2 beta` change had surfaced this: the eager STS call made the fast tests fail when creds were absent.)
- **Stale-doc fixes:** the bundle `CLAUDE.md` now references the real skills (`enrollment`/`financial`, was
  `academic-performance`/`enrollment-analytics`/`financial-analytics`) and only the 2 tables that exist
  (was 10). The duplicate `complete_code_sample/` is deleted.
- **Verified green:** M0 fast 6 + slow 4 (live S3/Athena); M1 fast 11 + slow 1 (agent queried Athena,
  "10,000 distinct students"); M2 fast 14 + live deploy→invoke (answered "3,594" + S3 upload + role IAM
  confirmed + trace in CloudWatch, zero manual steps); M3 fast 15 + live clarification round-trip (ambiguous
  "top 5 students" → clarification JSON + session id → answer "rank by GPA" with resume → GPA-ranked answer).
  All deploys torn down after.

## Current state (branch `refactoring`)

Done: archived old BI code → Module 1 → Module 2 (deploy, live-verified) → Module 4 (observability,
live-verified) → **Module 3 (memory), built + fast-tested + LIVE-VERIFIED end-to-end on us-west-2**
(deploy + cross-session recall round-trip; see Module 3 decisions above). Module 3 is **single-tenant**
and reuses the M2 bundle + the new `memory/session.py`; the `system_prompt_suffix` backport touched
Module 1's `agent.py` and was re-synced to all bundle copies (drift-guard still green). **All four
modules are committed/pushed to `origin/refactoring`** (through `a6ecdc8 refactor-phase-1`).

**Phase-2 cleanup (this session):** the four notebooks moved much of their command flow to `setup.sh`
+ `!command`/`subprocess` cells, which broke the static `test_code_cells_parse` (it `ast.parse`d `!`
lines). Fixed by skipping `!`/`%` lines in all four `tests/test_static.py`; removed a stray syntax-error
cell in `module-3-memory.ipynb` (`REGION=‘…’` smart-quotes). Separately, the three
`agentcore/.cli/deployed-state.json` files (which had captured a real account id + ARNs) are now
**untracked** (`.gitignore` drops the `!…deployed-state.json` exception; local files retained — the CDK
tolerates their absence). Fast tiers green after the fix: M1 33 · M2 16 · M3 31 · M4 15.

### Python version is pinned to 3.11 everywhere (parity)
Local dev, the deployed container, and the (cosmetic-for-Container) runtime config all say 3.11:
- **Local dev:** committed `.python-version` = `3.11.14` per MODULE folder (uv's native pin; `requires-python`
  is only a range and let the venvs drift to 3.12). `3.11.15` doesn't exist — 3.11.14 is the newest 3.11 build.
- **Deployed container:** bundle `Dockerfile` `FROM python:3.11-slim-trixie` — this is the ONLY thing that
  sets the deployed Python for a Container build. **Live-verified on us-west-2** (M2 deploy+invoke on the 3.11
  image passed, then torn down).
- **`agentcore.json` `runtimeVersion: PYTHON_3_11`** — set for consistency, but **the CDK IGNORES it for
  Container builds** (verified in `AgentCoreRuntime.js`: `runtimeVersion` only feeds the CodeZip
  `codeConfiguration.runtime`; Container uses just `containerConfiguration.containerUri`). The Dockerfile wins.
- Bundles keep `requires-python = ">=3.11"` (a floor, fine).

**Repo-wide reproducibility quirks — both RESOLVED this session:**
1. ✅ **`Dockerfile` un-ignored & committed.** Removed the global `Dockerfile` ignore so the three bundle
   Dockerfiles (now `python:3.11`) are tracked. A fresh clone now has them; `test_dockerfile_*` passes.
2. ✅ **CDK source `lib/cdk-stack.ts` un-ignored & committed.** It was swallowed by the Python-packaging
   `lib/` rule — but it's a CLI-scaffolded SOURCE file (identical to the `@aws/agentcore` template at
   `dist/assets/cdk/lib/cdk-stack.ts`), and its sibling `bin/cdk.ts` was already committed, so the two were
   inconsistent. Fix: anchored the ignore to `/lib/` (repo-root Python only) and committed the three
   `agentcore/cdk/lib/cdk-stack.ts`. `node_modules` stays ignored (install with `npm ci`), and each module's
   `setup.sh` runs `(cd agentcore/cdk && npm ci)` as a one-time pre-deploy step. A fresh clone can now deploy
   with just that `npm ci` — no more `sh: tsc: command not found`. (`cdk/dist/lib/` build output is still
   ignored via `cdk/.gitignore` `dist/`.)
