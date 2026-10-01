import re
import sys

UNITS = [("d", 86400), ("h", 3600), ("m", 60), ("s", 1)]
SPEC = re.compile(r"^\s*(?:(\d+)\s*d)?\s*(?:(\d+)\s*h)?\s*(?:(\d+)\s*m)?\s*(?:(\d+)\s*s)?\s*$", re.I)


def parse(spec: str) -> int:
    match = SPEC.match(spec)
    if not match or not any(match.groups()):
        raise ValueError(f"invalid duration: {spec!r}")
    return sum(int(n) * secs for n, (_, secs) in zip(match.groups(), UNITS) if n)


def format_seconds(total: int) -> str:
    if total < 0:
        raise ValueError("negative duration")
    parts = []
    for unit, secs in UNITS:
        n, total = divmod(total, secs)
        if n:
            parts.append(f"{n}{unit}")
    return "".join(parts) or "0s"


def main():
    try:
        if sys.argv[1] == "--format":
            print(format_seconds(int(sys.argv[2])))
        else:
            print(parse(" ".join(sys.argv[1:])))
    except (ValueError, IndexError) as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
