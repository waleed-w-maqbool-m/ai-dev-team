import statistics
import sys


def main():
    numbers = []
    for token in sys.stdin.read().split():
        try:
            numbers.append(float(token))
        except ValueError:
            print(f"error: invalid number: {token}", file=sys.stderr)
            sys.exit(1)
    if not numbers:
        print("error: no data", file=sys.stderr)
        sys.exit(1)
    print(f"count {len(numbers)}")
    print(f"mean {statistics.fmean(numbers):.2f}")
    print(f"median {statistics.median(numbers):.2f}")
    print(f"min {min(numbers):.2f}")
    print(f"max {max(numbers):.2f}")


if __name__ == "__main__":
    main()
