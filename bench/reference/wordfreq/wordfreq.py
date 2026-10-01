import argparse
import re
import sys
from collections import Counter


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("path")
    parser.add_argument("--top", type=int, default=10)
    args = parser.parse_args()
    try:
        with open(args.path, encoding="utf-8") as f:
            text = f.read()
    except FileNotFoundError:
        print(f"error: no such file: {args.path}", file=sys.stderr)
        sys.exit(1)
    counts = Counter(re.findall(r"[a-z]+", text.lower()))
    for word, n in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[: args.top]:
        print(word, n)


if __name__ == "__main__":
    main()
