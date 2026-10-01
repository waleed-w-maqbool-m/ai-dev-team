class Inventory:
    def __init__(self):
        self._stock: dict[str, int] = {}

    @staticmethod
    def _check_qty(qty):
        if not isinstance(qty, int) or isinstance(qty, bool) or qty <= 0:
            raise ValueError(f"quantity must be a positive integer, got {qty!r}")

    def add(self, sku: str, qty: int) -> None:
        self._check_qty(qty)
        self._stock[sku] = self._stock.get(sku, 0) + qty

    def remove(self, sku: str, qty: int) -> None:
        self._check_qty(qty)
        if sku not in self._stock:
            raise ValueError(f"unknown sku {sku!r}")
        if self._stock[sku] < qty:
            raise ValueError(f"only {self._stock[sku]} of {sku!r} in stock")
        self._stock[sku] -= qty
        if self._stock[sku] == 0:
            del self._stock[sku]

    def quantity(self, sku: str) -> int:
        return self._stock.get(sku, 0)

    def report(self) -> list[tuple[str, int]]:
        return sorted(self._stock.items())
