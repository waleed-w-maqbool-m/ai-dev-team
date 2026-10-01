import sys

from inventory import Inventory


def main():
    inv = Inventory()
    for line in sys.stdin:
        parts = line.split()
        if not parts:
            continue
        try:
            if parts[0] in ("add", "remove") and len(parts) == 3:
                getattr(inv, parts[0])(parts[1], int(parts[2]))
            elif parts == ["report"]:
                for sku, qty in inv.report():
                    print(sku, qty)
            else:
                raise ValueError(f"unknown command: {line.strip()}")
        except ValueError as e:
            print(f"error: {e}")


if __name__ == "__main__":
    main()
