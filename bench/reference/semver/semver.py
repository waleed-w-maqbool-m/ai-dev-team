import re
from functools import cmp_to_key

NUM = r"0|[1-9]\d*"
IDENT = r"[0-9A-Za-z-]+"
VERSION = re.compile(rf"^({NUM})\.({NUM})\.({NUM})(?:-({IDENT}(?:\.{IDENT})*))?(?:\+({IDENT}(?:\.{IDENT})*))?$")


def parse(version: str) -> tuple:
    m = VERSION.match(version)
    if not m:
        raise ValueError(f"invalid version: {version!r}")
    prerelease = ()
    if m.group(4):
        idents = m.group(4).split(".")
        for ident in idents:
            if ident.isdigit() and len(ident) > 1 and ident[0] == "0":
                raise ValueError(f"leading zero in {ident!r}")
        prerelease = tuple(int(i) if i.isdigit() else i for i in idents)
    return int(m.group(1)), int(m.group(2)), int(m.group(3)), prerelease


def _cmp_ident(a, b) -> int:
    if isinstance(a, int) and isinstance(b, int):
        return (a > b) - (a < b)
    if isinstance(a, int):
        return -1
    if isinstance(b, int):
        return 1
    return (a > b) - (a < b)


def compare(a: str, b: str) -> int:
    pa, pb = parse(a), parse(b)
    if pa[:3] != pb[:3]:
        return -1 if pa[:3] < pb[:3] else 1
    ra, rb = pa[3], pb[3]
    if not ra or not rb:
        return (not ra) - (not rb) if ra != rb else 0
    for x, y in zip(ra, rb):
        c = _cmp_ident(x, y)
        if c:
            return c
    return (len(ra) > len(rb)) - (len(ra) < len(rb))


def max_version(versions: list[str]) -> str:
    return max(versions, key=cmp_to_key(compare))
