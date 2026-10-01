"""Writes the data the static (GitHub Pages) console reads:

    frontend/public/replays/index.json   list of published replays
    frontend/public/benchmark.json       benchmark results (same as /api/benchmark)

Only replays already in frontend/public/replays/ are published. Pass
--publish-bench to copy every benchmark run's replay in first. Local runs
(memory/replays/) are never published automatically.

Usage: python scripts/export_static_data.py [--publish-bench]
"""
import argparse
import glob
import json
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bench.report import benchmark_json  # noqa: E402
from utils import replays  # noqa: E402

PUBLIC_DIR = os.path.join(replays.ROOT, "frontend", "public")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--publish-bench", action="store_true", help="publish all benchmark run replays")
    args = parser.parse_args()

    os.makedirs(replays.PUBLISHED_DIR, exist_ok=True)
    if args.publish_bench:
        for path in glob.glob(replays.BENCH_GLOB):
            with open(path, encoding="utf-8") as f:
                replay_id = json.load(f)["id"]
            shutil.copyfile(path, os.path.join(replays.PUBLISHED_DIR, f"{replay_id}.json"))

    published = []
    for path in sorted(glob.glob(os.path.join(replays.PUBLISHED_DIR, "*.json"))):
        if os.path.basename(path) == "index.json":
            continue
        with open(path, encoding="utf-8") as f:
            published.append(replays.meta(json.load(f)))
    published.sort(key=lambda r: r.get("recorded_at") or "", reverse=True)

    with open(os.path.join(replays.PUBLISHED_DIR, "index.json"), "w", encoding="utf-8") as f:
        json.dump(published, f, ensure_ascii=False, indent=1)
    with open(os.path.join(PUBLIC_DIR, "benchmark.json"), "w", encoding="utf-8") as f:
        json.dump(benchmark_json(), f, ensure_ascii=False, indent=1)
    print(f"Published {len(published)} replay(s); wrote benchmark.json")


if __name__ == "__main__":
    main()
