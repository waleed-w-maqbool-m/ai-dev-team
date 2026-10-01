import sys


def shift_text(key: str, text: str, direction: int) -> str:
    shifts = [ord(c) - ord("a") for c in key.lower()]
    out, k = [], 0
    for ch in text:
        if ch.isascii() and ch.isalpha():
            base = ord("A") if ch.isupper() else ord("a")
            out.append(chr((ord(ch) - base + direction * shifts[k % len(shifts)]) % 26 + base))
            k += 1
        else:
            out.append(ch)
    return "".join(out)


def main():
    if len(sys.argv) != 4 or sys.argv[1] not in ("encrypt", "decrypt"):
        print("usage: cipher.py encrypt|decrypt KEY TEXT", file=sys.stderr)
        sys.exit(1)
    mode, key, text = sys.argv[1:]
    if not (key.isascii() and key.isalpha()):
        print("error: KEY must contain only letters", file=sys.stderr)
        sys.exit(1)
    print(shift_text(key, text, 1 if mode == "encrypt" else -1))


if __name__ == "__main__":
    main()
