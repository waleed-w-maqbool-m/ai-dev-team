"""The benchmark suite: 12 requests, each with hidden tests the pipeline
never sees.

Each request pins down file names and the interface (CLI usage or function
signatures), the way a real spec would, so hidden tests can check behaviour
without caring how the code is organised inside. Tests are black-box: run
the generated program and compare stdout / exit code, or import the
generated module and print results. bench/reference/ holds a hand-written
solution for every task, and tests/test_bench_suite.py checks that each one
passes its own hidden tests, so the expected outputs here are themselves
verified.
"""
import json
from dataclasses import dataclass, field


@dataclass
class Case:
    """One hidden test: run `python <args>` in the workspace (with `files`
    written under it first, and `stdin` piped in) and compare."""
    name: str
    args: list[str]
    stdout: str | None = None   # exact match after stripping trailing whitespace per line
    json: object = None         # stdout parsed as JSON must equal this
    exit_code: int | None = 0   # None = don't care
    stdin: str | None = None
    files: dict[str, str] = field(default_factory=dict)
    prefix_match: bool = False  # each stdout line only has to start with the expected line

    def evaluate(self, returncode: int | None, out: str, err: str = "") -> tuple[bool, str]:
        if returncode is None:
            return False, "timed out"
        if self.exit_code is not None and returncode != self.exit_code:
            return False, f"exit code {returncode}, expected {self.exit_code}"
        if self.exit_code and "Traceback (most recent call last)" in err:
            # An uncaught exception also exits non-zero; the spec asks for a
            # handled error message, not a crash.
            return False, "crashed with a traceback instead of reporting the error"
        if self.stdout is not None and not _stdout_matches(out, self.stdout, self.prefix_match):
            return False, f"stdout {out.strip()[:200]!r}, expected {self.stdout!r}"
        if self.json is not None:
            try:
                got = json.loads(out)
            except ValueError:
                return False, f"stdout is not JSON: {out.strip()[:200]!r}"
            if got != self.json:
                return False, f"JSON {json.dumps(got)[:200]}, expected {json.dumps(self.json)[:200]}"
        return True, ""


@dataclass
class BenchTask:
    id: str
    difficulty: str  # easy | medium | hard
    request: str
    cases: list[Case]


def _norm(text: str) -> str:
    return "\n".join(line.rstrip() for line in text.strip().splitlines())


def _stdout_matches(out: str, expected: str, prefix_match: bool) -> bool:
    if not prefix_match:
        return _norm(out) == _norm(expected)
    got, want = _norm(out).splitlines(), _norm(expected).splitlines()
    return len(got) == len(want) and all(g.startswith(w) for g, w in zip(got, want))


def _py(code: str) -> list[str]:
    """Args for a library test: run a snippet that imports the generated module."""
    return ["-c", code]


TASKS: list[BenchTask] = [
    BenchTask(
        id="wordfreq",
        difficulty="easy",
        request=(
            "Write a Python CLI script `wordfreq.py`. Usage: `python wordfreq.py PATH [--top N]`. "
            "It reads the UTF-8 text file at PATH and splits it into words, where a word is a maximal "
            "run of ASCII letters a-z (case-insensitive) — so apostrophes, digits and punctuation are "
            "separators. Words are lowercased. Print the N most frequent words (default 10), one per "
            "line, as `word count` separated by a single space, ordered by count descending with ties "
            "broken alphabetically. If PATH does not exist, print an error message to stderr and exit "
            "with status 1."
        ),
        cases=[
            Case("basic", ["wordfreq.py", "_bench/a.txt", "--top", "2"],
                 stdout="the 3\ncat 2", files={"_bench/a.txt": "The cat and the hat. The CAT sat!\n"}),
            Case("ties alphabetical", ["wordfreq.py", "_bench/b.txt", "--top", "3"],
                 stdout="a 2\nb 2\nc 1", files={"_bench/b.txt": "b a c b a"}),
            Case("separators", ["wordfreq.py", "_bench/c.txt"],
                 stdout="don 2\nstop 1\nt 1", files={"_bench/c.txt": "don't stop 42 don"}),
            Case("default top 10", ["wordfreq.py", "_bench/d.txt"],
                 stdout="\n".join(f"{w} 1" for w in "abcdefghij"),
                 files={"_bench/d.txt": " ".join("abcdefghijkl")}),
            Case("missing file", ["wordfreq.py", "_bench/nope.txt"], exit_code=1),
        ],
    ),
    BenchTask(
        id="csv2json",
        difficulty="easy",
        request=(
            "Write a Python CLI script `csv2json.py`. Usage: `python csv2json.py PATH`. It reads the CSV "
            "file at PATH, whose first row is the header, and prints to stdout a JSON array with one "
            "object per data row mapping each header name to that row's value as a string (no type "
            "conversion). It must handle standard CSV quoting, including quoted fields that contain "
            "commas, double quotes and newlines. A file that is empty or has only a header row prints "
            "`[]`. If PATH does not exist, print an error message to stderr and exit with status 1."
        ),
        cases=[
            Case("basic", ["csv2json.py", "_bench/a.csv"],
                 json=[{"name": "Ann", "age": "30"}, {"name": "Bob", "age": "25"}],
                 files={"_bench/a.csv": "name,age\nAnn,30\nBob,25\n"}),
            Case("quoting", ["csv2json.py", "_bench/b.csv"],
                 json=[{"id": "1", "note": 'a, "quoted"\nline'}],
                 files={"_bench/b.csv": 'id,note\n1,"a, ""quoted""\nline"\n'}),
            Case("header only", ["csv2json.py", "_bench/c.csv"], json=[], files={"_bench/c.csv": "x,y\n"}),
            Case("empty file", ["csv2json.py", "_bench/d.csv"], json=[], files={"_bench/d.csv": ""}),
            Case("missing file", ["csv2json.py", "_bench/nope.csv"], exit_code=1),
        ],
    ),
    BenchTask(
        id="roman",
        difficulty="easy",
        request=(
            "Write a Python CLI script `roman.py` with two subcommands. `python roman.py to-roman N` "
            "prints the Roman numeral for the integer N, which must be between 1 and 3999, using standard "
            "subtractive notation (IV, IX, XL, XC, CD, CM). `python roman.py from-roman S` prints the "
            "integer value of the Roman numeral S, which must be uppercase and in canonical form (so "
            "IIII, IC and VX are invalid). For any invalid input — out-of-range or non-integer N, or an "
            "invalid numeral — print an error message to stderr and exit with status 2."
        ),
        cases=[
            Case("to-roman 1994", ["roman.py", "to-roman", "1994"], stdout="MCMXCIV"),
            Case("to-roman 3999", ["roman.py", "to-roman", "3999"], stdout="MMMCMXCIX"),
            Case("to-roman 4", ["roman.py", "to-roman", "4"], stdout="IV"),
            Case("from-roman", ["roman.py", "from-roman", "MCMXCIV"], stdout="1994"),
            Case("from-roman XLII", ["roman.py", "from-roman", "XLII"], stdout="42"),
            Case("zero", ["roman.py", "to-roman", "0"], exit_code=2),
            Case("4000", ["roman.py", "to-roman", "4000"], exit_code=2),
            Case("IIII", ["roman.py", "from-roman", "IIII"], exit_code=2),
            Case("IC", ["roman.py", "from-roman", "IC"], exit_code=2),
        ],
    ),
    BenchTask(
        id="calc",
        difficulty="hard",
        request=(
            "Write a Python CLI script `calc.py`, an arithmetic expression evaluator that must NOT use "
            "eval, exec, compile or the ast module. Usage: `python calc.py \"EXPR\"`. It supports "
            "non-negative integer and decimal literals, the binary operators + - * /, unary minus, and "
            "parentheses, with standard precedence and left associativity; whitespace is optional. If "
            "the result is a whole number, print it without a decimal point (e.g. `1`, `-10`); otherwise "
            "print it the way Python prints a float (e.g. `3.5`). On division by zero or a malformed "
            "expression, print an error message to stderr and exit with status 1."
        ),
        cases=[
            Case("precedence", ["calc.py", "2 + 3 * (4 - 1)"], stdout="11"),
            Case("division", ["calc.py", "7/2"], stdout="3.5"),
            Case("unary minus", ["calc.py", "-(2+3)*2"], stdout="-10"),
            Case("left assoc minus", ["calc.py", "10 - 4 - 3"], stdout="3"),
            Case("left assoc divide", ["calc.py", "8/4/2"], stdout="1"),
            Case("decimals", ["calc.py", "1.5 * 3"], stdout="4.5"),
            Case("divide by zero", ["calc.py", "1/0"], exit_code=1),
            Case("dangling operator", ["calc.py", "2 +"], exit_code=1),
            Case("unbalanced paren", ["calc.py", "(1+2"], exit_code=1),
        ],
    ),
    BenchTask(
        id="duration",
        difficulty="medium",
        request=(
            "Write a Python CLI script `duration.py`. `python duration.py SPEC` converts a duration such "
            "as `1h30m`, `45s`, `2d4h` or `1h 15m 10s` to a total number of seconds and prints it as an "
            "integer. Units are d (86400 s), h, m and s; each unit may appear at most once and units "
            "must appear in the order d, h, m, s; spaces between parts are allowed; units are "
            "case-insensitive. `python duration.py --format SECONDS` does the reverse: it prints the "
            "compact canonical form with no spaces, omitting zero units (5400 -> `1h30m`), and `0s` for "
            "zero. On invalid input, print an error message to stderr and exit with status 1."
        ),
        cases=[
            Case("h+m", ["duration.py", "1h30m"], stdout="5400"),
            Case("spaces", ["duration.py", "1h 15m 10s"], stdout="4510"),
            Case("uppercase", ["duration.py", "2D4H"], stdout="187200"),
            Case("format", ["duration.py", "--format", "5400"], stdout="1h30m"),
            Case("format zero", ["duration.py", "--format", "0"], stdout="0s"),
            Case("format all units", ["duration.py", "--format", "90061"], stdout="1d1h1m1s"),
            Case("wrong order", ["duration.py", "30m1h"], exit_code=1),
            Case("unknown unit", ["duration.py", "5x"], exit_code=1),
        ],
    ),
    BenchTask(
        id="logstats",
        difficulty="medium",
        request=(
            "Write a Python CLI script `logstats.py`. Usage: `python logstats.py PATH`. It reads a web "
            "server access log in Common Log Format, one request per line, for example: "
            "`127.0.0.1 - - [10/Oct/2000:13:55:36 -0700] \"GET /index.html HTTP/1.0\" 200 2326`. It "
            "prints a JSON object with these keys: `total_requests` (number of valid lines), "
            "`status_counts` (object mapping each status code, as a string, to its count), `top_paths` "
            "(list of up to 3 `[path, count]` pairs, most requested first, ties broken by path "
            "ascending), `bytes_sent` (sum of the size field, where `-` counts as 0), and "
            "`malformed_lines` (number of non-blank lines that don't match the format; they are "
            "otherwise ignored)."
        ),
        cases=[
            Case("mixed log", ["logstats.py", "_bench/access.log"],
                 json={
                     "total_requests": 6,
                     "status_counts": {"200": 4, "404": 1, "304": 1},
                     "top_paths": [["/index.html", 3], ["/a.png", 1], ["/missing", 1]],
                     "bytes_sent": 2326 * 3 + 512,
                     "malformed_lines": 2,
                 },
                 files={"_bench/access.log": "\n".join([
                     '127.0.0.1 - - [10/Oct/2000:13:55:36 -0700] "GET /index.html HTTP/1.0" 200 2326',
                     '10.0.0.2 - bob [10/Oct/2000:13:55:37 -0700] "GET /index.html HTTP/1.1" 200 2326',
                     'garbage line',
                     '10.0.0.3 - - [10/Oct/2000:13:55:38 -0700] "GET /missing HTTP/1.1" 404 -',
                     '10.0.0.3 - - [10/Oct/2000:13:55:39 -0700] "GET /a.png HTTP/1.1" 200 512',
                     '',
                     '10.0.0.4 - - [10/Oct/2000:13:55:40 -0700] "GET /index.html HTTP/1.1" 304 -',
                     '10.0.0.4 - - [10/Oct/2000:13:55:41 -0700] "POST /zz HTTP/1.1" 200 2326',
                     '10.0.0.5 - - [bad date] "GET /x HTTP/1.1" two hundred 5',
                 ]) + "\n"}),
            Case("empty log", ["logstats.py", "_bench/empty.log"],
                 json={"total_requests": 0, "status_counts": {}, "top_paths": [],
                       "bytes_sent": 0, "malformed_lines": 0},
                 files={"_bench/empty.log": ""}),
        ],
    ),
    BenchTask(
        id="urlparts",
        difficulty="medium",
        request=(
            "Write a Python CLI script `urlparts.py`. Usage: `python urlparts.py URL`. It prints a JSON "
            "object with keys `scheme`, `host` (lowercased), `port` (an integer; if the URL has none, "
            "use 80 for http, 443 for https, and null for any other scheme), `path` (`/` if empty), "
            "`query` (object mapping each query parameter name to the list of its values in order, "
            "percent-decoded; `{}` if there is no query) and `fragment` (string, or null if absent). If "
            "the URL has no scheme or no host, print an error message to stderr and exit with status 1."
        ),
        cases=[
            Case("full", ["urlparts.py", "https://Example.COM/a/b?x=1&y=2&x=3#top"],
                 json={"scheme": "https", "host": "example.com", "port": 443, "path": "/a/b",
                       "query": {"x": ["1", "3"], "y": ["2"]}, "fragment": "top"}),
            Case("explicit port", ["urlparts.py", "http://localhost:8080"],
                 json={"scheme": "http", "host": "localhost", "port": 8080, "path": "/",
                       "query": {}, "fragment": None}),
            Case("other scheme", ["urlparts.py", "ftp://files.example.org/pub/f.txt"],
                 json={"scheme": "ftp", "host": "files.example.org", "port": None, "path": "/pub/f.txt",
                       "query": {}, "fragment": None}),
            Case("percent decoding", ["urlparts.py", "http://h.io/s?q=a%20b&tag=c%26d"],
                 json={"scheme": "http", "host": "h.io", "port": 80, "path": "/s",
                       "query": {"q": ["a b"], "tag": ["c&d"]}, "fragment": None}),
            Case("no scheme", ["urlparts.py", "example.com/path"], exit_code=1),
        ],
    ),
    BenchTask(
        id="vigenere",
        difficulty="easy",
        request=(
            "Write a Python CLI script `cipher.py` implementing the Vigenère cipher. Usage: "
            "`python cipher.py encrypt KEY TEXT` or `python cipher.py decrypt KEY TEXT`, printing the "
            "result. KEY must contain only letters (case-insensitive); otherwise print an error message "
            "to stderr and exit with status 1. Each letter of TEXT is shifted by the corresponding key "
            "letter (A/a = 0 ... Z/z = 25), preserving the letter's case. Non-letter characters are "
            "copied unchanged and do NOT advance the position in the key."
        ),
        cases=[
            Case("classic", ["cipher.py", "encrypt", "LEMON", "ATTACKATDAWN"], stdout="LXFOPVEFRNHR"),
            Case("case and punctuation", ["cipher.py", "encrypt", "key", "Hello, World!"], stdout="Rijvs, Uyvjn!"),
            Case("decrypt", ["cipher.py", "decrypt", "key", "Rijvs, Uyvjn!"], stdout="Hello, World!"),
            Case("bad key", ["cipher.py", "encrypt", "k3y", "abc"], exit_code=1),
        ],
    ),
    BenchTask(
        id="stats",
        difficulty="easy",
        request=(
            "Write a Python CLI script `stats.py` that reads numbers (integers or floats, separated by "
            "any whitespace including newlines) from stdin and prints exactly five lines: `count N`, "
            "`mean X`, `median X`, `min X`, `max X`, where N is an integer and each X is formatted with "
            "exactly 2 decimal places. If there are no numbers, print `error: no data` to stderr and "
            "exit with status 1. If any token is not a number, print `error: invalid number: TOKEN` to "
            "stderr and exit with status 1."
        ),
        cases=[
            Case("odd count", ["stats.py"], stdin="3 1 2\n",
                 stdout="count 3\nmean 2.00\nmedian 2.00\nmin 1.00\nmax 3.00"),
            Case("even count, floats", ["stats.py"], stdin="1.5\n4\n  2 10\n",
                 stdout="count 4\nmean 4.38\nmedian 3.00\nmin 1.50\nmax 10.00"),
            Case("negatives", ["stats.py"], stdin="-5 -1",
                 stdout="count 2\nmean -3.00\nmedian -3.00\nmin -5.00\nmax -1.00"),
            Case("no data", ["stats.py"], stdin="   \n", exit_code=1),
            Case("bad token", ["stats.py"], stdin="1 two 3", exit_code=1),
        ],
    ),
    BenchTask(
        id="lru_cache",
        difficulty="medium",
        request=(
            "Create a Python module `lru_cache.py` defining a class `LRUCache` with: "
            "`__init__(self, capacity: int)`, raising ValueError if capacity is less than 1; "
            "`get(self, key)`, returning the stored value or None if the key is missing, where a hit "
            "makes the key the most recently used; `put(self, key, value)`, inserting or updating the "
            "key and making it the most recently used, and evicting the least recently used key when "
            "the cache would exceed its capacity; and `__len__(self)`. Do not use functools.lru_cache "
            "or any third-party library."
        ),
        cases=[
            Case("eviction order", _py(
                "from lru_cache import LRUCache\n"
                "c = LRUCache(2); c.put('a', 1); c.put('b', 2); c.get('a'); c.put('c', 3)\n"
                "print(c.get('a'), c.get('b'), c.get('c'), len(c))"), stdout="1 None 3 2"),
            Case("update refreshes", _py(
                "from lru_cache import LRUCache\n"
                "c = LRUCache(2); c.put('a', 1); c.put('b', 2); c.put('a', 10); c.put('c', 3)\n"
                "print(c.get('a'), c.get('b'), c.get('c'))"), stdout="10 None 3"),
            Case("capacity one", _py(
                "from lru_cache import LRUCache\n"
                "c = LRUCache(1); c.put(1, 'x'); c.put(2, 'y')\n"
                "print(c.get(1), c.get(2), len(c))"), stdout="None y 1"),
            Case("invalid capacity", _py(
                "from lru_cache import LRUCache\n"
                "try:\n    LRUCache(0)\nexcept ValueError:\n    print('ok')"), stdout="ok"),
        ],
    ),
    BenchTask(
        id="semver",
        difficulty="hard",
        request=(
            "Create a Python module `semver.py` implementing Semantic Versioning 2.0.0 with three "
            "functions. `parse(version: str) -> tuple` returns `(major, minor, patch, prerelease)` where "
            "major/minor/patch are ints and prerelease is a tuple of identifiers (int for purely numeric "
            "identifiers, str otherwise; an empty tuple if there is no prerelease). It raises ValueError "
            "for invalid versions: the core must be MAJOR.MINOR.PATCH of non-negative integers without "
            "leading zeros, optionally followed by `-` and dot-separated prerelease identifiers "
            "([0-9A-Za-z-]+, numeric ones without leading zeros); build metadata after `+` is allowed and "
            "ignored. `compare(a: str, b: str) -> int` returns -1, 0 or 1 using SemVer 2.0.0 precedence "
            "(a prerelease ranks below the release; identifiers compare left to right, numeric ones "
            "numerically and below alphanumeric ones, alphanumeric ones in ASCII order; if all "
            "preceding identifiers are equal, the shorter prerelease ranks lower). "
            "`max_version(versions: list[str]) -> str` returns the highest version in the list."
        ),
        cases=[
            Case("precedence chain", _py(
                "from semver import compare\n"
                "chain = ['1.0.0-alpha', '1.0.0-alpha.1', '1.0.0-alpha.beta', '1.0.0-beta',\n"
                "         '1.0.0-beta.2', '1.0.0-beta.11', '1.0.0-rc.1', '1.0.0']\n"
                "print(all(compare(a, b) == -1 and compare(b, a) == 1 for a, b in zip(chain, chain[1:])))"),
                stdout="True"),
            Case("numeric not lexical", _py(
                "from semver import compare\nprint(compare('2.0.0', '10.0.0'), compare('1.0.0-2', '1.0.0-10'))"),
                stdout="-1 -1"),
            Case("build metadata ignored", _py(
                "from semver import compare\nprint(compare('1.0.0+build.5', '1.0.0'))"), stdout="0"),
            Case("parse", _py(
                "from semver import parse\nprint(parse('1.2.3-rc.1+b'))"), stdout="(1, 2, 3, ('rc', 1))"),
            Case("invalid versions", _py(
                "from semver import parse\nbad = 0\n"
                "for v in ['1.2', '01.0.0', '1.0.0-', '1.0.0-01', 'a.b.c', '1.0.0-a..b']:\n"
                "    try:\n        parse(v)\n    except ValueError:\n        bad += 1\n"
                "print(bad)"), stdout="6"),
            Case("max_version", _py(
                "from semver import max_version\nprint(max_version(['1.0.0-rc.1', '0.9.9', '1.0.0', '1.0.0-beta']))"),
                stdout="1.0.0"),
        ],
    ),
    BenchTask(
        id="inventory",
        difficulty="hard",
        request=(
            "Build a small inventory tool as two Python files. `inventory.py` defines a class "
            "`Inventory` with: `add(sku: str, qty: int)`, where qty must be a positive integer "
            "(otherwise raise ValueError); `remove(sku: str, qty: int)`, raising ValueError if the sku "
            "is unknown, qty is not a positive integer, or there is not enough stock, and dropping the "
            "sku entirely when its quantity reaches 0; `quantity(sku: str) -> int`, returning 0 for "
            "unknown skus; and `report() -> list[tuple[str, int]]`, returning (sku, quantity) pairs "
            "sorted by sku. `inventory_cli.py` uses that class and reads commands from stdin, one per "
            "line: `add SKU QTY`, `remove SKU QTY` or `report`. `report` prints each item as `SKU QTY`, "
            "one per line. For an unknown or malformed command, or an operation that raises, print "
            "`error: ` followed by a message to stdout and continue with the next line. Blank lines are "
            "ignored. The CLI exits with status 0 at end of input."
        ),
        cases=[
            Case("cli session", ["inventory_cli.py"],
                 stdin="add widget 5\nadd bolt 10\nremove widget 2\n\nreport\n",
                 stdout="bolt 10\nwidget 3"),
            Case("cli errors continue", ["inventory_cli.py"],
                 stdin="remove ghost 1\nfly away\nadd nut -3\nadd nut 2\nreport\n",
                 stdout="error:\nerror:\nerror:\nnut 2", prefix_match=True),
            Case("remove to zero drops sku", _py(
                "from inventory import Inventory\n"
                "inv = Inventory(); inv.add('a', 2); inv.add('b', 1); inv.remove('a', 2)\n"
                "print(inv.report(), inv.quantity('a'))"), stdout="[('b', 1)] 0"),
            Case("insufficient stock", _py(
                "from inventory import Inventory\ninv = Inventory(); inv.add('a', 1)\n"
                "try:\n    inv.remove('a', 5)\nexcept ValueError:\n    print('ok', inv.quantity('a'))"),
                stdout="ok 1"),
        ],
    ),
]

TASKS_BY_ID = {t.id: t for t in TASKS}
