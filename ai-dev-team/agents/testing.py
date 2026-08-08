"""Testing Agent: executes the Software Engineer's just-written code and
records real pass/fail evidence — not another LLM judgment. Runs strictly
between swe and qa (architecture doc Section 20's proposed slot-in), and has
no routing authority: it only writes `task.test_report`, which QA then reads
alongside the code (utils/context.py::qa_context). This is the fix for the
pipeline's most-cited v1 weakness — QA used to review by inspection only and
never actually ran anything.

SAFETY: this runs code an LLM just wrote, as a real subprocess on the host,
scoped to AI_TEAM_WORKSPACE, with a hard per-check timeout. There is no
sandboxing/isolation beyond that — do not point AI_TEAM_WORKSPACE at a
location you would not want arbitrary generated code executing near.
"""
import ast
import os
import subprocess
import sys

from config import settings
from schemas.messages import AgentMessage, MessageType
from schemas.state import ProjectState
from schemas.testing import TestCheck, TestReport
from utils import context as ctx

SENDER = "testing_agent"

TARGET_PROJECT_DIR = os.environ.get("AI_TEAM_WORKSPACE", os.path.join(os.getcwd(), "workspace"))


def _check_syntax(full_path: str, rel_path: str) -> TestCheck:
    try:
        with open(full_path, "r", encoding="utf-8") as f:
            source = f.read()
        ast.parse(source, filename=rel_path)
        return TestCheck(file=rel_path, check="syntax", passed=True)
    except SyntaxError as e:
        return TestCheck(file=rel_path, check="syntax", passed=False, detail=f"line {e.lineno}: {e.msg}")


def _check_import(full_path: str, rel_path: str) -> TestCheck:
    module = os.path.splitext(os.path.basename(full_path))[0]
    try:
        result = subprocess.run(
            [sys.executable, "-c", f"import {module}"],
            cwd=TARGET_PROJECT_DIR,
            capture_output=True,
            text=True,
            timeout=settings.TEST_EXEC_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        return TestCheck(
            file=rel_path, check="import", passed=False,
            detail=f"timed out after {settings.TEST_EXEC_TIMEOUT_SECONDS}s",
        )
    if result.returncode == 0:
        return TestCheck(file=rel_path, check="import", passed=True)
    return TestCheck(file=rel_path, check="import", passed=False, detail=result.stderr.strip()[-500:])


def _check_smoke_run(full_path: str, rel_path: str) -> TestCheck | None:
    with open(full_path, "r", encoding="utf-8") as f:
        source = f.read()
    if "__main__" not in source:
        return None  # not a CLI entry point; nothing to smoke-run

    try:
        result = subprocess.run(
            [sys.executable, full_path, "--help"],
            cwd=TARGET_PROJECT_DIR,
            capture_output=True,
            text=True,
            timeout=settings.TEST_EXEC_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        return TestCheck(
            file=rel_path, check="smoke_run", passed=False,
            detail=f"timed out after {settings.TEST_EXEC_TIMEOUT_SECONDS}s",
        )

    # A clean run or a graceful argparse usage error both mean the entry
    # point starts up correctly; an unhandled traceback is a real defect.
    crashed = "Traceback (most recent call last)" in result.stderr
    return TestCheck(
        file=rel_path, check="smoke_run", passed=not crashed,
        detail="" if not crashed else result.stderr.strip()[-500:],
    )


def testing_node(state: ProjectState) -> dict:
    task = state.get_current_task()
    impl_payload = ctx.latest_implementation_payload(state, task.id)

    checks: list[TestCheck] = []
    for change in impl_payload.get("files_changed", []):
        if change.get("action") == "delete" or not change["path"].endswith(".py"):
            continue
        full_path = os.path.join(TARGET_PROJECT_DIR, change["path"])
        if not os.path.exists(full_path):
            continue

        syntax_check = _check_syntax(full_path, change["path"])
        checks.append(syntax_check)
        if not syntax_check.passed:
            continue  # importing/running unparseable code isn't meaningful

        checks.append(_check_import(full_path, change["path"]))
        smoke = _check_smoke_run(full_path, change["path"])
        if smoke:
            checks.append(smoke)

    failed = [c for c in checks if not c.passed]
    report = TestReport(
        task_id=task.id,
        status="fail" if failed else "pass",
        checks=checks,
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
