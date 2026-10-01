"""Single place to tune system behavior without touching agent code."""
import os


def _load_dotenv(path: str) -> None:
    """Minimal .env support (KEY=VALUE lines, # comments) so an API key can
    live in a gitignored file instead of the shell. Real environment
    variables always win."""
    if not os.path.isfile(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


_load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "ollama")  # "ollama" | "groq"

OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_CHAT_ENDPOINT = f"{OLLAMA_BASE_URL}/api/chat"
MODEL_NAME = os.environ.get("AI_TEAM_MODEL", "qwen3:8b")

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
GROQ_BASE_URL = os.environ.get(
    "GROQ_BASE_URL", "https://api.groq.com/openai/v1/chat/completions"
)
GROQ_MODEL_NAME = os.environ.get("GROQ_MODEL_NAME", "llama-3.3-70b-versatile")

MAX_TRANSPORT_RETRIES = int(os.environ.get("AI_TEAM_TRANSPORT_RETRIES", 3))  # network/timeout/429 retries per call
MAX_SCHEMA_RETRIES = 2          # re-prompt retries on invalid JSON / schema mismatch
MAX_REVIEW_ITERATIONS = 3       # QA fail-loop cap, per task
MAX_CLARIFICATION_ROUNDS = 2    # PM clarification-loop cap

# A 429 asking us to wait longer than this is a quota that won't reset soon
# (e.g. a daily token limit), so fail fast instead of sleeping for hours.
MAX_RATE_LIMIT_WAIT_SECONDS = 120

# LangGraph steps per run. Every loop is already capped (review and
# clarification caps above), so this only has to be comfortably above the
# longest legitimate run. Each task takes 4 steps (swe, testing, qa,
# pm_check) plus 3 per QA retry, so LangGraph's default of 25 is already
# exceeded by a 6-task plan, or a 4-task plan with two retries.
GRAPH_RECURSION_LIMIT = 500

# Turning the Testing Agent off sends swe straight to qa, i.e. QA reviews by
# inspection only (the original v1 behaviour). Exists for the benchmark's
# ablation; leave it on otherwise.
ENABLE_TESTING_AGENT = os.environ.get("AI_TEAM_TESTING", "on") != "off"

REQUEST_TIMEOUT_SECONDS = 600

# Testing Agent: how long a single subprocess check (import / smoke-run) may
# run before being killed. Real code execution, not an LLM call — kept short
# since it only needs to prove the entry point starts cleanly.
TEST_EXEC_TIMEOUT_SECONDS = 15

# Where those checks run (tools/sandbox.py): "auto" uses Docker when a daemon
# is reachable, else a scrubbed host subprocess; "docker" / "subprocess" force
# one. The image only needs a Python interpreter.
TEST_SANDBOX = os.environ.get("AI_TEAM_SANDBOX", "auto")
SANDBOX_IMAGE = os.environ.get("AI_TEAM_SANDBOX_IMAGE", "python:3.12-slim")


def workspace_dir() -> str:
    """Where generated files are written and executed. Read on every call
    rather than once at import, so tests and the benchmark runner can point
    each run at its own directory via AI_TEAM_WORKSPACE."""
    return os.path.abspath(
        os.environ.get("AI_TEAM_WORKSPACE", os.path.join(os.getcwd(), "workspace"))
    )


PROMPTS_DIR = os.path.join(os.path.dirname(__file__), "..", "prompts")
MEMORY_DB_PATH = os.path.join(os.path.dirname(__file__), "..", "memory", "project_state.db")

LOG_DIR = os.path.join(os.path.dirname(__file__), "..", "memory", "logs")
