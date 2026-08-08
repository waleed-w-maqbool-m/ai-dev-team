"""Unit tests for the Testing Agent's real (non-LLM) execution checks: a
syntax error must fail the report, and a clean file — with and without a CLI
entry point — must pass. Runs in an isolated temp workspace so it never
touches the real workspace/ folder."""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_WORKSPACE = tempfile.mkdtemp(prefix="ai_team_test_workspace_")
os.environ["AI_TEAM_WORKSPACE"] = _WORKSPACE  # must be set before importing agents.testing

from agents.testing import testing_node  # noqa: E402
from schemas.implementation import FileAction  # noqa: E402
from schemas.messages import AgentMessage, MessageType  # noqa: E402
from schemas.state import ProjectState  # noqa: E402
from schemas.task import AcceptanceCriterion, Task  # noqa: E402


def _state_for(task_id: str, path: str, content: str) -> ProjectState:
    task = Task(
        id=task_id,
        title="Test task",
        description="Exists only to exercise the Testing Agent.",
        acceptance_criteria=[AcceptanceCriterion(id="AC1", description="File runs")],
    )
    state = ProjectState.new(user_request="n/a")
    state.tasks = [task]
    state.current_task_id = task_id
    impl_msg = AgentMessage(
        sender="software_engineer",
        message_type=MessageType.implementation,
        payload={
            "task_id": task_id,
            "files_changed": [{"path": path, "action": FileAction.create.value, "content": content}],
        },
    )
    state.messages = [impl_msg]
    os.makedirs(_WORKSPACE, exist_ok=True)
    with open(os.path.join(_WORKSPACE, path), "w", encoding="utf-8") as f:
        f.write(content)
    return state


def test_syntax_error_fails():
    state = _state_for("T1", "broken.py", "def broken(:\n    pass\n")
    updates = testing_node(state)
    report = updates["tasks"][0].test_report
    assert report.status == "fail"
    assert any(c.check == "syntax" and not c.passed for c in report.checks)
    print("syntax-error case: FAIL as expected —", report.summary)


def test_clean_module_passes():
    state = _state_for("T2", "clean_lib.py", "def add(a, b):\n    return a + b\n")
    updates = testing_node(state)
    report = updates["tasks"][0].test_report
    assert report.status == "pass"
    assert any(c.check == "syntax" and c.passed for c in report.checks)
    assert any(c.check == "import" and c.passed for c in report.checks)
    assert not any(c.check == "smoke_run" for c in report.checks), "no __main__, so no smoke-run expected"
    print("clean library case: PASS as expected —", report.summary)


def test_cli_entry_point_smoke_runs():
    content = (
        "import argparse\n"
        "if __name__ == '__main__':\n"
        "    parser = argparse.ArgumentParser()\n"
        "    parser.parse_args()\n"
    )
    state = _state_for("T3", "cli_tool.py", content)
    updates = testing_node(state)
    report = updates["tasks"][0].test_report
    assert report.status == "pass"
    assert any(c.check == "smoke_run" and c.passed for c in report.checks)
    print("CLI entry-point case: PASS as expected —", report.summary)


def main():
    test_syntax_error_fails()
    test_clean_module_passes()
    test_cli_entry_point_smoke_runs()
    print("\nALL ASSERTIONS PASSED")


if __name__ == "__main__":
    main()
