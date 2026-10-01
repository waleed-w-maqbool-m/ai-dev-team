"""Keeps the benchmark honest: every task's hidden tests must pass against
its hand-written reference solution and fail against an empty workspace,
so a score reflects the generated code, not a broken expected output."""
import os
import shutil

import pytest

from bench.hidden import run_hidden_tests
from bench.tasks import TASKS
from tools import sandbox

REFERENCE_DIR = os.path.join(os.path.dirname(__file__), "..", "bench", "reference")


@pytest.mark.parametrize("task", TASKS, ids=lambda t: t.id)
def test_reference_solution_passes_every_hidden_test(task, tmp_path):
    shutil.copytree(os.path.join(REFERENCE_DIR, task.id), tmp_path, dirs_exist_ok=True)
    result = run_hidden_tests(task, str(tmp_path), sandbox.active_backend())
    assert result["failures"] == []


@pytest.mark.parametrize("task", TASKS, ids=lambda t: t.id)
def test_empty_workspace_fails_every_hidden_test(task, tmp_path):
    result = run_hidden_tests(task, str(tmp_path), sandbox.active_backend())
    assert result["passed"] == 0, [c.name for c in task.cases]


def test_task_ids_are_unique_and_have_references():
    ids = [t.id for t in TASKS]
    assert len(ids) == len(set(ids))
    assert sorted(ids) == sorted(os.listdir(REFERENCE_DIR))
