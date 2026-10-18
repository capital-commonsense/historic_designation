"""Standardize DC street addresses to comparable keys: '1518 K ST NW'.

Nomination addresses are free text ('1132, 1140, and 1146 3rd Street, SE',
'3500-3510 Minnesota Avenue SE'); permit and lot addresses are already in the
city's 'NUMBER STREET SUFFIX QUADRANT' form. Both are reduced to the same keys.
"""

import re

SUFFIXES = {
    "STREET": "ST", "AVENUE": "AVE", "AV": "AVE", "PLACE": "PL", "ROAD": "RD", "TERRACE": "TER",
    "DRIVE": "DR", "COURT": "CT", "CIRCLE": "CIR", "BOULEVARD": "BLVD", "PARKWAY": "PKWY",
    "LANE": "LN", "SQUARE": "SQ", "WAY": "WAY", "ALLEY": "ALY", "PLAZA": "PLZ", "CRESCENT": "CRES",
}
QUADRANTS = ("NW", "NE", "SW", "SE")
MAX_RANGE = 80  # house numbers spanned by one range; wider ones are blocks, not buildings

_NUMS = r"\d+[A-Z]?(?:\s*-\s*\d+)?"
_ADDRESS = re.compile(
    rf"(?P<nums>{_NUMS}(?:\s*(?:,|AND|&)\s*(?:AND\s+)?{_NUMS})*)"
    r"(?:\s*\((?:ODD|EVEN)[^)]*\))?\s+"
    r"(?P<street>(?:[A-Z0-9]+\s+){0,3}?[A-Z0-9]+?)\s+"
    rf"(?P<suffix>{'|'.join(sorted(set(SUFFIXES) | set(SUFFIXES.values()), key=len, reverse=True))})\b"
    r"\.?,?\s*(?P<quad>NW|NE|SW|SE)\b"
)


def _house_numbers(nums: str) -> list[str]:
    out = []
    for part in re.split(r"\s*(?:,|AND|&)\s*(?:AND\s+)?", nums):
        m = re.fullmatch(r"(\d+)[A-Z]?(?:\s*-\s*(\d+))?", part.strip())
        if not m:
            continue
        lo, hi = int(m.group(1)), int(m.group(2) or m.group(1))
        if hi < lo or hi - lo > MAX_RANGE:
            out.append(str(lo))
            continue
        # Same parity at both ends means one side of the street.
        step = 2 if (hi - lo) % 2 == 0 else 1
        out.extend(str(n) for n in range(lo, hi + 1, step))
    return out


def keys(text) -> list[str]:
    """Every standardized address in the text, house-number ranges and lists expanded."""
    if not isinstance(text, str):
        return []
    t = re.sub(r"\^\((\w+)\)", r"\1", text.upper())  # '14^(th)' from PDF superscripts
    t = re.sub(r"[^\w\s,&()-]", " ", t)
    t = re.sub(r"\b(\d+)(ST|ND|RD|TH)\b", r"\1", t)  # '3rd Street' and '3RD ST' -> '3 ST'
    t = re.sub(r"\b([NS])\s+([EW])\b", r"\1\2", t)  # 'N.W.'
    t = re.sub(r"\s+", " ", t)
    out = []
    for m in _ADDRESS.finditer(t):
        street = f"{m.group('street')} {SUFFIXES.get(m.group('suffix'), m.group('suffix'))} {m.group('quad')}"
        out.extend(f"{n} {street}" for n in _house_numbers(m.group("nums")))
    return list(dict.fromkeys(out))
