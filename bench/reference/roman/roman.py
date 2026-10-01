import sys

NUMERALS = [(1000, "M"), (900, "CM"), (500, "D"), (400, "CD"), (100, "C"), (90, "XC"),
            (50, "L"), (40, "XL"), (10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I")]


def to_roman(n: int) -> str:
    if not 1 <= n <= 3999:
        raise ValueError("out of range")
    out = []
    for value, symbol in NUMERALS:
        while n >= value:
            out.append(symbol)
            n -= value
    return "".join(out)


def from_roman(s: str) -> int:
    total, i = 0, 0
    for value, symbol in NUMERALS:
        while s.startswith(symbol, i):
            total += value
            i += len(symbol)
    # Canonical form round-trips exactly; anything else (IIII, IC, VX) doesn't.
    if i != len(s) or not s or to_roman(total) != s:
        raise ValueError("invalid numeral")
    return total


def main():
    try:
        cmd, arg = sys.argv[1], sys.argv[2]
        if cmd == "to-roman":
            print(to_roman(int(arg)))
        elif cmd == "from-roman":
            print(from_roman(arg))
        else:
            raise ValueError(f"unknown command {cmd}")
    except (ValueError, IndexError) as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
