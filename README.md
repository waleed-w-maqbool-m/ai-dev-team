# AI Development Team

A 5-agent software engineering pipeline (Project Manager → Software Engineer →
Testing Agent → QA Reviewer → Documentation Agent), built on **LangGraph**.
The LLM backend is pluggable — run entirely locally against **Ollama**
(default: **Qwen3 8B**), or point it at **Groq**'s free hosted API to run on
their inference hardware instead. This is the reference implementation of the
architecture described in `ai-dev-team-architecture.md`.

## How it works, in one paragraph

You give it a request. The Project Manager breaks it into tasks with
acceptance criteria. For each task, the Software Engineer implements it, the
Testing Agent actually runs the code (syntax, import, and entry-point checks —
real subprocess execution, not an LLM opinion), and QA reviews it against the
acceptance criteria *with that executed evidence in hand* — QA can send it
back for up to 3 retries before the task is set aside for human review, so the
loop can never run forever. If the Engineer hits something genuinely
ambiguous, it asks the PM, which resolves it using the original request
(bounded to 2 rounds, same reasoning). Once every task is done or set aside,
the Documentation Agent writes the README/changelog updates and a final
summary. All routing decisions are plain Python reading structured state —
never a second LLM call guessing what to do next.

## Setup

```bash
pip install -r requirements.txt
```

Then pick an LLM backend:

**Option A — Ollama (local, fully offline, needs a decent GPU or patience on CPU)**

```bash
ollama pull qwen3:8b
ollama serve   # if not already running as a service
```

No further configuration needed — `LLM_PROVIDER` defaults to `ollama`.

**Option B — Groq (hosted, free tier, no local hardware requirements)**

```bash
# Get a free API key: https://console.groq.com/keys
export GROQ_API_KEY=your-key-here     # PowerShell: $env:GROQ_API_KEY="your-key-here"
export LLM_PROVIDER=groq              # PowerShell: $env:LLM_PROVIDER="groq"
```

Defaults to `llama-3.3-70b-versatile`; override with `GROQ_MODEL_NAME` to use
a different model from Groq's catalog (check `console.groq.com/docs/models`
for current model IDs, since hosted lineups change over time). Groq's free
tier is rate-limited (not unlimited), so a large multi-task run may pause
briefly if a limit is hit — the pipeline's existing transport-retry backoff
absorbs this automatically.

## Usage

```bash
python main.py "Build a CLI tool that converts CSV files to JSON."
```

This will:
- Plan and implement the request, writing files under `workspace/` (override
  with the `AI_TEAM_WORKSPACE` env var to point at a real project checkout
  instead).
- Persist run state to `memory/project_state.db` (via LangGraph's SQLite
  checkpointer), so an interrupted run can be resumed by reusing the same
  `thread_id`.
- Log the full agent message audit trail as JSONL to `memory/logs/`.
- Print a task-by-task status summary and the final user-facing summary.

### Configuration

Everything tunable lives in `config/settings.py` — LLM provider, model
names, Ollama/Groq URLs, retry caps, timeouts. Per-agent sampling
temperatures live on `RunConfig` in `schemas/state.py` if you want different
values per run (PM/QA default low for consistency, the Engineer defaults
slightly higher).

## Web console

`api.py` serves a local dashboard (`dashboard/index.html`) with a live view
of the pipeline running against a real request, streamed over Server-Sent
Events — a Console page (agent-by-agent progress, generated files), an About
page, and Run Logs / Analytics pages backed by real runs (stored in your
browser, not fabricated data).

```bash
pip install -r requirements.txt   # includes fastapi/uvicorn
python api.py
# open http://127.0.0.1:8000
```

Binds to `127.0.0.1` only — never expose this on `0.0.0.0` or the public
internet. The Testing Agent executes generated code as a real subprocess,
which is a reasonable risk to accept on your own machine and a bad one to
accept from strangers on the internet.

## Running the tests

The test suite mocks the LLM layer (`agents.base.BaseAgent.run`) so it runs
without a live Ollama server, and exercises the parts of the system that are
easy to get subtly wrong:

```bash
python tests/test_pipeline_mock.py   # full happy-path run: clarification
                                       # round, QA fail-then-pass, a 2-task
                                       # dependency chain, and doc generation
python tests/test_review_cap.py       # confirms the QA retry cap actually
                                       # bounds the loop (task ends up
                                       # blocked_needs_human, not infinite)
python tests/test_testing_agent.py    # Testing Agent's real (non-LLM) checks:
                                       # a syntax error fails the report; a
                                       # clean module and a clean CLI entry
                                       # point both pass
```

Both scripts assert on the resulting `ProjectState` and exit non-zero on
failure — wire them into CI or a pre-commit hook as-is.

## Project structure

See `ai-dev-team-architecture.md` for the full rationale. Short version:

| Folder | Contains |
|---|---|
| `agents/` | One node function per agent (`schemas/*` in, `dict` of state updates out) — including `testing.py`, the only agent that isn't an LLM call |
| `prompts/` | Raw system prompt text, editable without touching Python |
| `graph/` | LangGraph wiring (`build_graph.py`) and routing logic (`routing.py`) — the only place control-flow decisions are made |
| `models/` | `LLMClient` interface + `OllamaClient`/`GroqClient` implementations, selected by `models/factory.py` — schema-validated retries live once on the shared base class |
| `schemas/` | Every Pydantic I/O contract — the source of truth for what agents produce |
| `tools/` | Side-effecting operations (currently: applying file changes to disk) |
| `memory/` | SQLite checkpoints + JSONL message logs (gitignored, regenerated per run) |
| `config/` | All tunables in one file |
| `utils/` | Context-slicing policy (`context.py`) and the message logger (`logging.py`) |
| `tests/` | Mocked end-to-end tests — no live Ollama required |
| `dashboard/` | The local web console's HTML/CSS/JS (single file, no build step) |
| `api.py` | Local-only FastAPI server: serves the dashboard and streams real runs over SSE |

## Known limitations (v1)

- Tasks are processed sequentially — no parallel execution.
- The clarification-resolution path re-plans by replacing the entire task
  list rather than surgically patching one task; fine for a single
  clarification round, worth revisiting if you extend the clarification cap.
- The Testing Agent runs real syntax/import/entry-point checks (see
  `agents/testing.py`), so QA no longer reviews by inspection alone — but it
  is **not sandboxed**: checks execute as subprocesses directly on the host,
  scoped to `AI_TEAM_WORKSPACE`, with a timeout and nothing else. Don't point
  `AI_TEAM_WORKSPACE` at anything you wouldn't want LLM-generated code running
  near. It also doesn't run a real test suite (pytest, etc.) against the
  code's actual behavior — only that it parses, imports, and starts cleanly.
