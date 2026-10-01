# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository layout

Run all commands from the repository root.

## Commands

```bash
# Setup
pip install -r requirements.txt

# Pick an LLM backend (LLM_PROVIDER defaults to "ollama"):
ollama pull qwen3:8b && ollama serve   # local, or:
export GROQ_API_KEY=...; export LLM_PROVIDER=groq   # hosted, free tier

# Run the pipeline against a request
python main.py "Build a CLI tool that converts CSV files to JSON."

# Run the test suite (mocks the LLM layer, no live Ollama required)
python tests/test_pipeline_mock.py  # full happy path: clarification round,
                                     # QA fail-then-pass, 2-task dependency
                                     # chain, doc generation
python tests/test_review_cap.py     # confirms the QA retry cap bounds the
                                     # loop (task ends up blocked_needs_human,
                                     # not infinite)
python tests/test_testing_agent.py  # Testing Agent's real (non-LLM) checks:
                                     # syntax error fails, clean module and
                                     # clean CLI entry point both pass
```

There is no separate lint/typecheck config in this repo — these two scripts are the whole test suite; both assert on the resulting `ProjectState` and exit non-zero on failure.

Output workspace defaults to `./workspace/` (override with `AI_TEAM_WORKSPACE`). Runtime state (`memory/project_state.db`, `memory/logs/`) is gitignored and regenerated per run.

## Architecture

This is a 5-agent software engineering pipeline — Project Manager → Software Engineer → Testing Agent → QA Reviewer → Documentation Agent — built on **LangGraph**. The LLM backend is pluggable (`LLM_PROVIDER=ollama|groq`, default `ollama` running **Qwen3 8B** locally; `groq` runs against Groq's free hosted API instead). The full design rationale lives in `ai-dev-team-architecture.md`; treat the code as authoritative where it has since diverged from that doc — it predates the `LLMClient` provider abstraction and the Testing Agent described below (Section 20 only *proposes* Testing as a future extension; it's since been implemented, not just proposed).

The Testing Agent (`agents/testing.py`) is the one agent in this pipeline that is **not an LLM call** — it's a deterministic node that runs real subprocess checks (syntax parse, import, and a `--help` smoke-run for anything with a `__main__` guard) against whatever the Software Engineer just wrote, and writes a `TestReport` onto the task. It has no routing authority — QA still makes the sole pass/fail call, just with that report as input (`utils/context.py::qa_context`) instead of code inspection alone. This directly replaces the old "QA reviews by inspection only" limitation; see the safety caveat in Known Limitations before pointing `AI_TEAM_WORKSPACE` at anything sensitive.

**Four principles that shape every design decision here** (worth internalizing before changing agent/routing code):
1. **One shared model, many roles.** A single `LLMClient` instance (backed by whichever provider is configured) is reused for every agent; role identity comes entirely from system prompt + temperature + output schema, not separate model instances.
2. **Blackboard over chatter.** Agents never call each other directly. They only read/write a single shared `ProjectState` object. Adding agent-to-agent messaging would break this pattern — don't.
3. **Determinism by construction.** All control-flow (pass/fail, next task, done/not-done) is decided by plain Python in `graph/routing.py` reading structured Pydantic fields — never by a second LLM call interpreting free text. This is what keeps an 8B model usable in a deterministic pipeline.
4. **Small-model-aware context discipline.** Each agent gets the *minimum* context slice for its task via `utils/context.py`, not the full `ProjectState` history.

### Agent lifecycle

Every agent node follows the same five-step lifecycle, implemented once in `agents/base.py::BaseAgent` and specialized only by prompt file, output schema, and temperature:

1. **Slice** — `utils/context.py` extracts the role-scoped view of `ProjectState` (e.g. `swe_context`, `qa_context`) — the single auditable place that decides "who sees what."
2. **Render** — sliced context + the schema (as JSON-schema text, repeated in the user turn — this measurably improves small-model JSON conformance) is appended to the fixed system prompt from `prompts/*.md`.
3. **Invoke** — `agents/base.py` gets a client from `models/factory.py::get_client()`, which reads `settings.LLM_PROVIDER` and returns either `models/ollama_client.py::OllamaClient` (calls Ollama's `/api/chat` with `format="json"`) or `models/groq_client.py::GroqClient` (calls Groq's OpenAI-compatible chat completions endpoint with `response_format={"type": "json_object"}`). Both implement the shared `models/llm_client.py::LLMClient` interface; `call_structured` (the validate-and-retry loop below) lives once on that base class, not duplicated per provider.
4. **Validate** — response is parsed into the agent's Pydantic output model (`schemas/*.py`); on `ValidationError` or bad JSON, re-prompt with the error appended, up to `MAX_SCHEMA_RETRIES`. No agent may skip this step — it's what keeps malformed output from silently propagating.
5. **Commit** — the node function merges the validated output back into `ProjectState`, appends an `AgentMessage` to `state.messages`, and returns.

`agents.base.BaseAgent.run` is the single seam every agent calls through — `tests/test_pipeline_mock.py` monkeypatches exactly this method to run the whole graph without a live Ollama server.

### Graph and routing (`graph/`)

`graph/build_graph.py` is wiring only. `graph/routing.py` holds every routing function (`route_after_swe`, `route_after_qa`, `route_after_pm_check`) — this is the *only* place control-flow decisions are made. If you're tracing "why did it go here instead of there," start in `routing.py`, not in an agent module.

Nodes: `pm_plan`, `swe`, `testing`, `qa`, `pm_check`, `docs`. `pm_plan` and `pm_check` are the same underlying Project Manager agent invoked in different modes (planning vs. status-check/re-plan) — kept as two graph nodes so routing stays simple conditionals instead of one node with a mode flag threaded through. `swe → testing` is a conditional edge (via `route_after_swe`, alongside the clarification/blocked branches); `testing → qa` is a plain unconditional edge, since testing never decides routing — only QA does.

Two bounded loops guarantee termination regardless of model behavior:
- **QA fail-loop**: capped at `state.config.max_review_iterations` (default 3, tracked per-task in `state.review_iterations`). On cap, the task becomes `blocked_needs_human` and the PM moves on to the next task rather than deadlocking the run.
- **PM clarification-loop**: capped at `state.config.max_clarification_rounds` (default 2, tracked in `state.clarification_rounds`). On cap, PM makes a best-effort assumption and proceeds rather than blocking indefinitely.

### State (`schemas/state.py`)

`ProjectState` is the single blackboard — the sole source of truth agents read/write. Each graph node is the sole writer for its turn (LangGraph's sequential execution guarantees no concurrent writes). Key fields: `tasks`, `current_task_id`, `project_status` (`ProjectStatus` enum), `review_iterations`, `clarification_rounds`, `pending_clarification`, `messages` (full audit trail), `documentation`, `final_summary`, `config` (a `RunConfig` — per-run tunables including per-agent temperatures).

Persistence is via LangGraph's `SqliteSaver` checkpointer (`memory/project_state.db`), keyed by `thread_id` — reusing a `thread_id` resumes an interrupted run. This is separate from the JSONL message audit log written by `utils/logging.py` to `memory/logs/`.

### Extending the pipeline

Adding a new agent (Research, DevOps, etc.) is meant to be additive, not disruptive — see architecture doc Section 20 for the specific slot-in points (Testing has already been added this way; see above). The recipe is always: add a schema in `schemas/`, add an agent module + prompt file (unless the agent is a deterministic tool node like `testing.py`, which needs no prompt), add a node + edge(s) in `graph/build_graph.py` and a branch in the relevant `graph/routing.py` function. Existing agents/nodes should not need to change.

### Prompts (`prompts/`)

Kept as raw `.md` text, separate from `agents/`, specifically so prompt iteration — the highest-churn part of this system — never requires a Python change or code review. Each prompt ends with an explicit instruction to return JSON matching the target schema and nothing else.

### Configuration

Everything tunable (LLM provider, Ollama/Groq URLs and model names, retry caps, timeouts) lives in `config/settings.py`, overridable via env vars (`LLM_PROVIDER`, `OLLAMA_BASE_URL`, `AI_TEAM_MODEL`, `GROQ_API_KEY`, `GROQ_BASE_URL`, `GROQ_MODEL_NAME`, `AI_TEAM_WORKSPACE`). Per-agent sampling temperatures live on `RunConfig` in `schemas/state.py` instead, since they can vary per run.

### Adding another LLM provider

Add a class in `models/` implementing `LLMClient.call()` (see `models/groq_client.py` for the shortest example), register it in `models/factory.py`'s `_PROVIDERS` dict, and add any needed settings to `config/settings.py`. No agent or graph code changes — every agent only depends on the `LLMClient` interface.

## Known limitations (v1)

- Tasks are processed strictly sequentially — no parallel task execution.
- Clarification resolution re-plans by replacing the entire task list rather than surgically patching one task.
- The Testing Agent executes generated code as a real subprocess directly on the host, scoped to `AI_TEAM_WORKSPACE`, with a timeout — **not sandboxed/isolated**. Don't point `AI_TEAM_WORKSPACE` at anything you wouldn't want LLM-generated code running near. It also only checks that code parses, imports, and starts cleanly — it doesn't run a real test suite against actual behavior.
