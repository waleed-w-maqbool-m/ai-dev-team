import json
import re
import sys
from collections import Counter

LINE = re.compile(r'^(\S+) (\S+) (\S+) \[([^\]]+)\] "(\S+) (\S+) (\S+)" (\d{3}) (\d+|-)$')


def main():
    statuses, paths = Counter(), Counter()
    total = bytes_sent = malformed = 0
    with open(sys.argv[1], encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            m = LINE.match(line)
            if not m:
                malformed += 1
                continue
            total += 1
            statuses[m.group(8)] += 1
            paths[m.group(6)] += 1
            bytes_sent += 0 if m.group(9) == "-" else int(m.group(9))
    top = sorted(paths.items(), key=lambda kv: (-kv[1], kv[0]))[:3]
    print(json.dumps({
        "total_requests": total,
        "status_counts": dict(statuses),
        "top_paths": [list(p) for p in top],
        "bytes_sent": bytes_sent,
        "malformed_lines": malformed,
    }))


if __name__ == "__main__":
    main()
