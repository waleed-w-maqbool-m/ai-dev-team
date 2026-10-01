import csv
import json
import sys


def main():
    if len(sys.argv) != 2:
        print("usage: csv2json.py PATH", file=sys.stderr)
        sys.exit(1)
    try:
        with open(sys.argv[1], newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
    except FileNotFoundError:
        print(f"error: no such file: {sys.argv[1]}", file=sys.stderr)
        sys.exit(1)
    print(json.dumps(rows))


if __name__ == "__main__":
    main()
