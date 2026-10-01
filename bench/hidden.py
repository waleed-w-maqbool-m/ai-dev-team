"""Runs a task's hidden tests against whatever is in a workspace directory.
Generated code is executed through the same sandbox as the Testing Agent."""
import os

from bench.tasks import BenchTask
from tools import sandbox


def run_hidden_tests(task: BenchTask, workspace: str, backend: str) -> dict:
    failures = []
    for case in task.cases:
        for rel_path, content in case.files.items():
            full = os.path.join(workspace, rel_path)
            os.makedirs(os.path.dirname(full), exist_ok=True)
            with open(full, "w", encoding="utf-8", newline="") as f:
                f.write(content)
        script = case.args[0]
        if script.endswith(".py") and not os.path.isfile(os.path.join(workspace, script)):
            # Otherwise Python's own "can't open file" exit status (2) would
            # satisfy a case that expects the program to exit 2.
            failures.append({"case": case.name, "detail": f"{script} was not created", "stderr": ""})
            continue
        result = sandbox.run_python(case.args, backend, stdin=case.stdin, workspace=workspace)
        ok, detail = case.evaluate(result.returncode, result.stdout, result.stderr)
        if not ok:
            failures.append({"case": case.name, "detail": detail, "stderr": result.stderr.strip()[-300:]})
    total = len(task.cases)
    return {"passed": total - len(failures), "total": total, "failures": failures}
