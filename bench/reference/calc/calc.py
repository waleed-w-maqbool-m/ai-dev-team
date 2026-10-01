import re
import sys

TOKEN = re.compile(r"\s*(?:(\d+\.\d*|\.\d+|\d+)|(.))")


def tokenize(expr):
    tokens = []
    for number, op in TOKEN.findall(expr):
        if number:
            tokens.append(float(number))
        elif op.strip():
            if op not in "+-*/()":
                raise ValueError(f"unexpected character {op!r}")
            tokens.append(op)
    return tokens


class Parser:
    def __init__(self, tokens):
        self.tokens, self.i = tokens, 0

    def peek(self):
        return self.tokens[self.i] if self.i < len(self.tokens) else None

    def take(self):
        tok = self.peek()
        if tok is None:
            raise ValueError("unexpected end of expression")
        self.i += 1
        return tok

    def expr(self):
        value = self.term()
        while self.peek() in ("+", "-"):
            value = value + self.term() if self.take() == "+" else value - self.term()
        return value

    def term(self):
        value = self.factor()
        while self.peek() in ("*", "/"):
            if self.take() == "*":
                value *= self.factor()
            else:
                divisor = self.factor()
                if divisor == 0:
                    raise ZeroDivisionError("division by zero")
                value /= divisor
        return value

    def factor(self):
        tok = self.take()
        if tok == "-":
            return -self.factor()
        if tok == "(":
            value = self.expr()
            if self.take() != ")":
                raise ValueError("expected )")
            return value
        if isinstance(tok, float):
            return tok
        raise ValueError(f"unexpected {tok!r}")


def main():
    try:
        parser = Parser(tokenize(sys.argv[1]))
        value = parser.expr()
        if parser.peek() is not None:
            raise ValueError(f"unexpected {parser.peek()!r}")
    except (ValueError, ZeroDivisionError, IndexError) as e:
        print(f"error: {e}", file=sys.stderr)
        sys.exit(1)
    print(int(value) if value == int(value) else value)


if __name__ == "__main__":
    main()
