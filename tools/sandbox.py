"""Runs Python inside the workspace for the Testing Agent — the one place
this system executes code a model just wrote.

Two backends, picked by settings.TEST_SANDBOX:
- "docker": a throwaway container with no network, a read-only root and a
  read-only workspace mount, no Linux capabilities, a non-root user, and
  memory / CPU / process limits. This is the real isolation.
- "subprocess": a host process with a scrubbed environment (no API keys
  or other secrets inherited), no stdin, and the same timeout. This is
  NOT isolation — the code can still touch the host filesystem and network.
"auto" (the default) uses docker when a daemon is reachable and falls back
to subprocess otherwise; every TestReport records which one actually ran.
"""
import functools
import os
import subprocess
import sys
import uuid
from dataclasses import dataclass

from config import settings

# Host env vars passed through in subprocess mode: just enough for Python to
# start on each OS. Everything else (GROQ_API_KEY, cloud credentials, ...)
# stays out of reach of generated code.
_SAFE_ENV_KEYS = ("PATH", "SYSTEMROOT", "TEMP", "TMP", "TMPDIR", "LANG", "LC_ALL")


@dataclass
class RunResult:
    returncode: int | None  # None means it was killed at the timeout
    stdout: str
    stderr: str

    @property
    def timed_out(self) -> bool:
        return self.returncode is None


@functools.lru_cache(maxsize=1)
def docker_available() -> bool:
    """True if a Docker daemon answers and the sandbox image is present
    (pulled here once, so the first real check isn't eaten by the timeout)."""
    try:
        if subprocess.run(["docker", "info"], capture_output=True, timeout=20).returncode != 0:
            return False
        image = settings.SANDBOX_IMAGE
        if subprocess.run(["docker", "image", "inspect", image], capture_output=True, timeout=20).returncode == 0:
            return True
        return subprocess.run(["docker", "pull", image], capture_output=True, timeout=600).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def active_backend() -> str:
    mode = settings.TEST_SANDBOX
    if mode == "subprocess":
        return "subprocess"
    if mode == "docker":
        if not docker_available():
            raise RuntimeError(
                "AI_TEAM_SANDBOX=docker but no Docker daemon is reachable "
                f"(or {settings.SANDBOX_IMAGE} could not be pulled)."
            )
        return "docker"
    if mode == "auto":
        return "docker" if docker_available() else "subprocess"
    raise ValueError(f"Unknown AI_TEAM_SANDBOX: {mode!r} (expected auto, docker or subprocess)")


def docker_command(workspace: str, args: list[str], name: str, interactive: bool = False) -> list[str]:
    return [
        "docker", "run", "--rm", "--name", name, *(["-i"] if interactive else []),
        "--network", "none",
        "--read-only", "--tmpfs", "/tmp:size=16m",
        "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
        "--user", "65534:65534",
        "--memory", "256m", "--cpus", "1", "--pids-limit", "64",
        "-e", "PYTHONDONTWRITEBYTECODE=1",
        "-v", f"{workspace}:/workspace:ro", "-w", "/workspace",
        settings.SANDBOX_IMAGE, "python", *args,
    ]


def run_python(
    args: list[str], backend: str, stdin: str | None = None, workspace: str | None = None
) -> RunResult:
    """Runs `python <args>` with the workspace (default: the configured one)
    as the working directory, feeding it `stdin` if given (otherwise stdin
    is closed)."""
    workspace = workspace or settings.workspace_dir()
    timeout = settings.TEST_EXEC_TIMEOUT_SECONDS

    if backend == "docker":
        name = f"ai-team-check-{uuid.uuid4().hex[:12]}"
        cmd, cwd, env = docker_command(workspace, args, name, interactive=stdin is not None), None, None
    else:
        name = None
        cmd, cwd = [sys.executable, *args], workspace
        env = {k: os.environ[k] for k in _SAFE_ENV_KEYS if k in os.environ}
        env.update(PYTHONDONTWRITEBYTECODE="1", PYTHONUTF8="1")

    try:
        proc = subprocess.run(
            cmd, cwd=cwd, env=env, capture_output=True, text=True, timeout=timeout,
            encoding="utf-8", errors="replace",
            **({"input": stdin} if stdin is not None else {"stdin": subprocess.DEVNULL}),
        )
    except subprocess.TimeoutExpired as e:
        if name:
            # Killing the docker CLI doesn't stop the container it started.
            subprocess.run(["docker", "kill", name], capture_output=True, timeout=30)
        return RunResult(None, _text(e.stdout), _text(e.stderr))
    return RunResult(proc.returncode, proc.stdout, proc.stderr)


def _text(value: str | bytes | None) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value or ""
