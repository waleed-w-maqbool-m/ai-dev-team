import json
import sys
from urllib.parse import parse_qs, urlsplit

DEFAULT_PORTS = {"http": 80, "https": 443}


def main():
    parts = urlsplit(sys.argv[1])
    if not parts.scheme or not parts.hostname:
        print("error: URL needs a scheme and a host", file=sys.stderr)
        sys.exit(1)
    print(json.dumps({
        "scheme": parts.scheme,
        "host": parts.hostname.lower(),
        "port": parts.port or DEFAULT_PORTS.get(parts.scheme),
        "path": parts.path or "/",
        "query": parse_qs(parts.query),
        "fragment": parts.fragment or None,
    }))


if __name__ == "__main__":
    main()
