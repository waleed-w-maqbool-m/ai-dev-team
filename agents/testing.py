"""Testing Agent: executes the Software Engineer's just-written code and
records real pass/fail evidence — not another LLM judgment. Runs strictly
between swe and qa (architecture doc Section 20's proposed slot-in), and has
no routing authority: it only writes `task.test_report`, which QA then reads
alongside the code (utils/context.py::qa_context). This is the fix for the
pipeline's most-cited v1 weakness — QA used to review by inspection only and
never actually ran anything.

SAFETY: this runs code an LLM just wrote. Execution goes through
tools/sandbox.py — a locked-down Docker container when available, otherwise
a host subprocess with a scrubbed environment (not isolated; see that
module). Each report records which backend ran.
"""
import ast
import os

from config import settings
from schemas.messages import AgentMessage, MessageType
from schemas.state import ProjectState
from schemas.testing import TestCheck, TestReport
from tools import sandbox
from tools.filesystem import resolve_in_workspace
from utils import context as ctx

SENDER = "testing_agent"


def _check_syntax(source: str, rel_path: str) -> TestCheck:
    try:
        ast.parse(source, filename=rel_path)
        return TestCheck(file=rel_path, check="syntax", passed=True)
    except SyntaxError as e:
        return TestCheck(file=rel_path, check="syntax", passed=False, detail=f"line {e.lineno}: {e.msg}")


def _module_name(rel_path: str) -> str | None:
    """"pkg/mod.py" -> "pkg.mod"; None if the path isn't importable as a
    module (e.g. "my-script.py"), in which case only the smoke run applies."""
    parts = os.path.normpath(os.path.splitext(rel_path)[0]).split(os.sep)
    if parts[-1] == "__init__":
        parts = parts[:-1]
    if not parts or not all(p.isidentifier() for p in parts):
        return None
    return ".".join(parts)


def _from_run(rel_path: str, check: str, result: sandbox.RunResult, passed: bool) -> TestCheck:
    if result.timed_out:
        return TestCheck(
            file=rel_path, check=check, passed=False,
            detail=f"timed out after {settings.TEST_EXEC_TIMEOUT_SECONDS}s",
        )
    return TestCheck(file=rel_path, check=check, passed=passed, detail="" if passed else result.stderr.strip()[-500:])


def _check_import(module: str, rel_path: str, backend: str) -> TestCheck:
    result = sandbox.run_python(["-c", f"import {module}"], backend)
    return _from_run(rel_path, "import", result, passed=result.returncode == 0)


def _check_smoke_run(rel_path: str, backend: str) -> TestCheck:
    result = sandbox.run_python([rel_path.replace(os.sep, "/"), "--help"], backend)
    # A clean run or a graceful argparse usage error both mean the entry
    # point starts up correctly; an unhandled traceback is a real defect.
    crashed = "Traceback (most recent call last)" in result.stderr
    return _from_run(rel_path, "smoke_run", result, passed=not crashed)


def testing_node(state: ProjectState) -> dict:
    task = state.get_current_task()
    impl_payload = ctx.latest_implementation_payload(state, task.id)
    backend = sandbox.active_backend()

    checks: list[TestCheck] = []
    for change in impl_payload.get("files_changed", []):
        rel_path = change["path"]
        if change.get("action") == "delete" or not rel_path.endswith(".py"):
            continue
        full_path = resolve_in_workspace(settings.workspace_dir(), rel_path)
        if full_path is None or not os.path.isfile(full_path):
            continue
        with open(full_path, "r", encoding="utf-8") as f:
            source = f.read()

        syntax_check = _check_syntax(source, rel_path)
        checks.append(syntax_check)
        if not syntax_check.passed:
            continue  # importing/running unparseable code isn't meaningful

        module = _module_name(rel_path)
        if module:
            checks.append(_check_import(module, rel_path, backend))
        if "__main__" in source:
            checks.append(_check_smoke_run(rel_path, backend))

    failed = [c for c in checks if not c.passed]
    report = TestReport(
        task_id=task.id,
        status="fail" if failed else "pass",
        checks=checks,
        sandbox=backend,
        summary=(
            f"{len(checks) - len(failed)}/{len(checks)} checks passed"
            if checks else "No executable Python files for this task."
        ),
    )

    updated_task = task.model_copy(update={"test_report": report})

    msg = AgentMessage(
        sender=SENDER,
        message_type=MessageType.test_report,
        payload=report.model_dump(mode="json"),
    )

    return {
        "tasks": state.with_task_updated(updated_task),
        "messages": state.append_message(msg),
    }
