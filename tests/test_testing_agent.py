"""The Testing Agent's real (non-LLM) checks. These run generated code for
real — under Docker when a daemon is available (as in CI), otherwise as a
scrubbed host subprocess."""
import os
import time

import pytest

from agents import testing as testing_agent
from config import settings
from schemas.implementation import FileAction
from schemas.messages import AgentMessage, MessageType
from schemas.state import ProjectState
from schemas.task import AcceptanceCriterion, Task
from tools import sandbox


def _report_for(files: dict[str, str]):
    """Writes `files` into the workspace, runs the Testing Agent on them as
    one task's implementation, and returns its TestReport."""
    workspace = settings.workspace_dir()
    for path, content in files.items():
        full = os.path.join(workspace, path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8") as f:
            f.write(content)

    state = ProjectState.new(user_request="n/a")
    state.tasks = [Task(id="T1", title="t", description="t",
                        acceptance_criteria=[AcceptanceCriterion(id="AC1", description="runs")])]
    state.current_task_id = "T1"
    state.messages = [AgentMessage(
        sender="software_engineer",
        message_type=MessageType.implementation,
        payload={"task_id": "T1", "files_changed": [
            {"path": p, "action": FileAction.create.value, "content": c} for p, c in files.items()
        ]},
    )]
    return testing_agent.testing_node(state)["tasks"][0].test_report


def _check(report, check):
    return next(c for c in report.checks if c.check == check)


def test_syntax_error_fails():
    report = _report_for({"broken.py": "def broken(:\n    pass\n"})
    assert report.status == "fail"
    assert [c.check for c in report.checks] == ["syntax"]


def test_clean_module_passes_without_a_smoke_run():
    report = _report_for({"clean_lib.py": "def add(a, b):\n    return a + b\n"})
    assert report.status == "pass"
    assert [c.check for c in report.checks] == ["syntax", "import"]


def test_cli_entry_point_smoke_runs():
    report = _report_for({"cli_tool.py": (
        "import argparse\n"
        "if __name__ == '__main__':\n"
        "    argparse.ArgumentParser().parse_args()\n"
    )})
    assert report.status == "pass"
    assert _check(report, "smoke_run").passed


def test_crashing_entry_point_fails_the_smoke_run():
    report = _report_for({"crash.py": "if __name__ == '__main__':\n    1 / 0\n"})
    assert report.status == "fail"
    assert "ZeroDivisionError" in _check(report, "smoke_run").detail


def test_nested_module_is_imported_by_its_dotted_path():
    report = _report_for({
        "pkg/__init__.py": "",
        "pkg/helpers.py": "from pkg import other\nVALUE = other.X\n",
        "pkg/other.py": "X = 1\n",
    })
    assert report.status == "pass", report.checks


def test_non_identifier_script_name_skips_import_but_still_smoke_runs():
    report = _report_for({"my-script.py": "if __name__ == '__main__':\n    print('hi')\n"})
    assert [c.check for c in report.checks] == ["syntax", "smoke_run"]
    assert report.status == "pass"


def test_code_waiting_on_stdin_fails_fast_instead_of_hanging():
    start = time.monotonic()
    report = _report_for({"asks.py": "name = input('name? ')\n"})
    assert report.status == "fail"
    assert "EOFError" in _check(report, "import").detail
    assert time.monotonic() - start < settings.TEST_EXEC_TIMEOUT_SECONDS


def test_report_records_which_sandbox_ran():
    report = _report_for({"ok.py": "x = 1\n"})
    assert report.sandbox == sandbox.active_backend()


def test_subprocess_mode_does_not_leak_secrets_to_generated_code(monkeypatch):
    monkeypatch.setattr(settings, "TEST_SANDBOX", "subprocess")
    monkeypatch.setenv("GROQ_API_KEY", "gsk_should_never_be_visible")
    report = _report_for({"snoop.py": "import os\nassert 'GROQ_API_KEY' not in os.environ\n"})
    assert report.status == "pass", report.checks


def test_docker_command_locks_the_container_down():
    cmd = sandbox.docker_command("/ws", ["-c", "pass"], "n")
    joined = " ".join(cmd)
    for flag in ["--network none", "--read-only", "--cap-drop ALL", "--user 65534:65534",
                 "--pids-limit", "--memory", "/ws:/workspace:ro"]:
        assert flag in joined, flag


@pytest.mark.skipif(not sandbox.docker_available(), reason="no Docker daemon")
def test_docker_sandbox_blocks_network_and_workspace_writes(monkeypatch):
    monkeypatch.setattr(settings, "TEST_SANDBOX", "docker")
    report = _report_for({
        "net.py": "import socket\nsocket.create_connection(('1.1.1.1', 53), timeout=3)\n",
        "write.py": "open('pwned.txt', 'w').write('x')\n",
    })
    assert report.sandbox == "docker"
    assert all(not c.passed for c in report.checks if c.check == "import")
    assert not os.path.exists(os.path.join(settings.workspace_dir(), "pwned.txt"))
