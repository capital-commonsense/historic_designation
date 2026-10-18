"""Classify nominators into filer types using inputs/filer_rules.csv.

A nominator string may name several co-filers ("X and Y", "X, Y, and Z",
"X on behalf of Y"); each part is classified, then combined:
  - an owner together with any non-owner  -> owner_cosponsor
  - otherwise the first filer's type (first-named filer is treated as primary)
"neighborhood" is resolved to neighborhood_society / neighborhood_adhoc later,
from each group's nomination count. All classifications are inferred from names.
"""

import re

import pandas as pd

from historic_preservation.config import INPUTS

SPLIT = re.compile(r",?\s+and\s+|,\s+|\s+on behalf of\s+|;\s*", re.I)
# Phrases whose internal "and"/"," must not split a filer name.
PROTECT = re.compile(
    r"Parks and Recreation|Planning and Economic Development|Tenants and Allies|,\s*Inc\.|& Employees"
    r"|Supreme Council, 33rd Degree, Southern Jurisdiction"
    r"|owners?\s+[A-Z][\w’']+\s+and\s+[A-Z][\w’']+(?:\s+[A-Z][\w’']+)?",
    re.I,
)
INSTITUTION = re.compile(r"\b(llc|lp|inc|corp|corporation|partners|partnership|church|university|library|club|"
                         r"institute|institution|society|hospitality|esop|redemptorists|government|owners, inc|"
                         r"convention|association|council|museum|foundation|trust|company|bank|navy|army|service)\b", re.I)
PERSON = re.compile(r"^[A-Z][a-z’']+(?:\s+[A-Z]\.?)?(?:\s+[A-Z][\w’']+)*(?:\s+and\s+[A-Z][a-z’']+(?:\s+[A-Z][\w’']+)*)?$")


def _private(name: str) -> bool:
    """Looks like a person's name rather than an organization (kept out of outputs)."""
    return bool(PERSON.match(name)) and len(name.split()) >= 2 and not INSTITUTION.search(name)


def load_rules() -> pd.DataFrame:
    return pd.read_csv(INPUTS / "filer_rules.csv").sort_values("order")


def classify_one(name: str, rules: pd.DataFrame) -> tuple[str, str, int | None]:
    clean = re.sub(r"\s+", " ", name).strip()
    clean = re.sub(r"^(the|by)\s+", "", clean, flags=re.I)
    for r in rules.itertuples():
        if re.search(r.pattern, clean, re.I):
            canonical = r.canonical_name if isinstance(r.canonical_name, str) and r.canonical_name else clean
            if r.filer_type == "anc":
                cid = re.search(r"(\d)\s*-?\s*([A-G])\b", clean)
                canonical = f"ANC {cid.group(1)}{cid.group(2)}" if cid else "ANC"
            if r.filer_type == "owner":
                canonical = re.sub(r"\s*\((?:property\s+)?owners?\)", "", clean, flags=re.I)  # "LCOR (owner)"
                canonical = re.sub(r"^(property\s+)?owners?\s*", "", canonical, flags=re.I).strip("() ") or "owner"
                if _private(canonical):
                    canonical = "private owner"
            return r.filer_type, canonical, int(r.order)
    return "other", ("individual" if _private(clean) else clean), None


def classify(nominated_by: str, rules: pd.DataFrame | None = None) -> dict:
    rules = load_rules() if rules is None else rules
    if not isinstance(nominated_by, str) or not nominated_by.strip():
        return {"filer_type": "unknown", "filers": "", "filer_types": "", "co_filers": "", "rule_ids": ""}
    guarded = PROTECT.sub(lambda m: m.group(0).replace(" and ", " \x00 ").replace(",", "\x01"), nominated_by.strip())
    parts = [p.replace(" \x00 ", " and ").replace("\x01", ",") for p in SPLIT.split(guarded) if p and p.strip()]
    # "with the homeowners" / "(with ...)" add an owner co-sponsor
    if re.search(r"with the homeowners|\(with", nominated_by, re.I):
        parts = [re.sub(r"\(with.*?\)|with the homeowners", "", p).strip() for p in parts] + ["property owners"]
    results = [classify_one(p, rules) for p in parts if p.strip()]
    types = [t for t, _, _ in results]
    if "owner" in types and any(t != "owner" for t in types):
        primary = "owner_cosponsor"
    else:
        primary = types[0]
    names = list(dict.fromkeys(n for _, n, _ in results))  # dedupe, keep order
    return {
        "filer_type": primary,
        "filers": "; ".join(names),
        "filer_types": "; ".join(types),
        "co_filers": "; ".join(names[1:]),
        "rule_ids": "; ".join(str(i) for _, _, i in results),
    }
