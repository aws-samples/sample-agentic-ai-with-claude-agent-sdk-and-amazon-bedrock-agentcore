# Skill output reference (fallback)

A **known-good result** of running the `ac-evaluation-transform` skill on this module's
`analytics_agent/` bundle. Provided so you can complete the module **without the Claude Code CLI**.

The point of Module 4, Step 1 is to *watch the skill instrument the agent yourself*. Use this
folder only if you can't run Claude Code:

```bash
cp skill_output_reference/*.py skill_output_reference/Dockerfile analytics_agent/
```

That drops in the four files the skill would have produced/edited:

| File | Role |
|------|------|
| `observability.py` | **new** — Strands-compatible spans + I/O-summary logs + metrics; no-op unless `AGENT_OBSERVABILITY_ENABLED` |
| `agent.py` | registers the `PreToolUse` / `PostToolUse` hooks in `build_agent_options()` |
| `agent_agentcore.py` | streams via `observability.run_instrumented()`; 2-arg `context` entrypoint |
| `Dockerfile` | disables the openinference auto-instrumentor (`OTEL_PYTHON_DISABLED_INSTRUMENTATIONS`) |
