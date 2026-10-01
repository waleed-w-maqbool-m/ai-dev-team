"""Benchmark runner: runs the pipeline on every task in bench/tasks.py under
one configuration, scores the output with hidden tests, and appends one
JSON line per run to bench/results/<name>.jsonl.

Runs are resumable — (task, repeat) pairs already in the results file are
skipped unless --force — so a run cut short by a provider's daily quota can
be continued later with the same command.

Examples:
    python -m bench.run --name llama-3.3-70b --provider groq --model llama-3.3-70b-versatile
    python -m bench.run --name llama-3.1-8b --provider groq --model llama-3.1-8b-instant
    python -m bench.run --name llama-3.1-8b-no-testing --provider groq \\
        --model llama-3.1-8b-instant --testing off
    python -m bench.report   # rebuild bench/RESULTS.md from all results
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone

from bench.hidden import run_hidden_tests
from bench.tasks import TASKS, TASKS_BY_ID
from tools import sandbox

BENCH_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(BENCH_DIR)
RESULTS_DIR = os.path.join(BENCH_DIR, "results")
RUNS_DIR = os.path.join(BENCH_DIR, "runs")


def _done_keys(results_path: str) -> set[tuple[str, int]]:
    if not os.path.exists(results_path):
        return set()
    with open(results_path, encoding="utf-8") as f:
        return {(r["task"], r["repeat"]) for r in map(json.loads, f) if not r["pipeline"].get("quota_exhausted")}


def _run_pipeline(task, workspace: str, log_path: str, env: dict, timeout: int) -> dict:
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "bench.worker", log_path],
            input=task.request, capture_output=True, text=True, encoding="utf-8",
            cwd=REPO_ROOT, env={**env, "AI_TEAM_WORKSPACE": workspace}, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return {"error": f"pipeline timed out after {timeout}s", "quota_exhausted": False}
    lines = proc.stdout.strip().splitlines()
    try:
        return json.loads(lines[-1])
    except (IndexError, ValueError):
        return {"error": f"worker crashed: {proc.stderr.strip()[-1000:]}", "quota_exhausted": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--name", required=True, help="results file name, e.g. llama-3.3-70b")
    parser.add_argument("--provider", default="groq", choices=["groq", "ollama"])
    parser.add_argument("--model", required=True)
    parser.add_argument("--testing", default="on", choices=["on", "off"], help="Testing Agent on/off (ablation)")
    parser.add_argument("--tasks", default="", help="comma-separated task ids (default: all)")
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--timeout", type=int, default=1800, help="seconds per pipeline run")
    parser.add_argument("--force", action="store_true", help="re-run tasks already in the results file")
    args = parser.parse_args()

    tasks = [TASKS_BY_ID[t] for t in args.tasks.split(",")] if args.tasks else TASKS
    os.makedirs(RESULTS_DIR, exist_ok=True)
    results_path = os.path.join(RESULTS_DIR, f"{args.name}.jsonl")
    done = set() if args.force else _done_keys(results_path)

    model_var = "GROQ_MODEL_NAME" if args.provider == "groq" else "AI_TEAM_MODEL"
    env = {
        **os.environ,
        "LLM_PROVIDER": args.provider,
        model_var: args.model,
        "AI_TEAM_TESTING": args.testing,
        "AI_TEAM_TRANSPORT_RETRIES": os.environ.get("AI_TEAM_TRANSPORT_RETRIES", "6"),
    }
    backend = sandbox.active_backend()
    config = {"name": args.name, "provider": args.provider, "model": args.model,
              "testing_agent": args.testing, "sandbox": backend}
    print(f"[bench] {args.name}: {args.provider}/{args.model}, testing={args.testing}, sandbox={backend}")

    for repeat in range(args.repeats):
        for task in tasks:
            if (task.id, repeat) in done:
                print(f"[bench] {task.id} r{repeat}: already in results, skipping")
                continue
            run_dir = os.path.join(RUNS_DIR, args.name, f"{task.id}-r{repeat}")
            shutil.rmtree(run_dir, ignore_errors=True)
            workspace = os.path.join(run_dir, "workspace")
            os.makedirs(workspace)

            pipeline = _run_pipeline(task, workspace, os.path.join(run_dir, "messages.jsonl"), env, args.timeout)
            if pipeline.get("quota_exhausted"):
                print(f"[bench] provider quota exhausted during {task.id}: {pipeline['error']}")
                print("[bench] stopping; re-run the same command later to resume.")
                return
            hidden = run_hidden_tests(task, workspace, backend)

            record = {
                "config": config, "task": task.id, "difficulty": task.difficulty, "repeat": repeat,
                "pipeline": pipeline, "hidden": hidden,
                "finished_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            }
            with open(results_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record) + "\n")
            status = "SOLVED" if hidden["passed"] == hidden["total"] else "partial" if hidden["passed"] else "failed"
            print(f"[bench] {task.id} r{repeat}: {status} {hidden['passed']}/{hidden['total']} hidden tests | "
                  f"pipeline {pipeline.get('tasks_done', 0)}/{pipeline.get('tasks_planned', 0)} tasks done, "
                  f"{pipeline.get('llm_calls', 0)} LLM calls, {pipeline.get('seconds', 0)}s"
                  + (f" | error: {pipeline['error'][:120]}" if pipeline.get("error") else ""))


if __name__ == "__main__":
    main()
