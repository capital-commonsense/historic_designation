"""Reconcile nominations across sources into nominations.csv (+ reconciliation.csv).

There is no single docket. Each source contributes partial records:
  hprb       HPRB actions (case no., meeting date, outcome, vote)    c. 2008+
  update     Inventory updates / HPO reports (nominator, date)        FY2010+
  manual     hand-read rows (inputs/manual_designations.csv)
  inventory  2009 Inventory designation entries (date only)           to 2009
  report     outcomes named in annual reports (inputs/report_outcomes.csv)
  dcpl       DCPL's posted list of its pending nominations
  hpo_pending HPO's list of pending nominations (case numbers)
  notice     noticed nominations HPRB never acted on (inputs/unheard_nominations.csv)

Records are merged on case number when both have one, otherwise on name
similarity (token_set_ratio >= 90) within a date window. A merged row lists
every source it was seen in; rows seen in only one source are written to
reconciliation.csv for review. Outcomes from later actions win over earlier
ones for the same case (e.g. continued, then designated).
"""

import re

import pandas as pd
from rapidfuzz import fuzz

from historic_preservation.config import INPUTS, JOINED, NORMALIZED, snapshot_dir
from historic_preservation.normalize.filers import classify, load_rules

OUTCOME_RANK = {"designated": 5, "denied": 5, "withdrawn": 5, "de-designated": 6, "amended": 4,
                "pending": 1, "continued": 2, "unclear": 0, "adopted": 3, "nr_only": 3,
                "not_heard": 2}
DATE_FMT = "%B %d, %Y"


GENERIC_ALIAS = re.compile(r"proposed|amend|expan|boundar|interior|demolish|revis|technical|additional|continu", re.I)


def aliases(s) -> str:
    """Names given in parentheses, e.g. 'Park Vista and Pine Manor (Concord Apartments)'.

    Only multi-word, non-generic ones: '(proposed)' or '(and Interiors)' would match anything.
    """
    found = [norm(a) for a in re.findall(r"\((.*?)\)", str(s or "")) if not GENERIC_ALIAS.search(a)]
    return " ".join(a for a in found if len(a.split()) >= 2)


def norm(s) -> str:
    s = str(s or "").lower().replace("’", "'")
    s = re.sub(r"\(.*?\)|\[.*?\]", " ", s)
    s = re.sub(r"\b(the|and|of|historic|landmark|nomination|memorial|monument|statue)\b|[^a-z0-9 ]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


ADDR_MIN_SCORE = 50  # token_set_ratio; lowest true address match seen is 50, highest false 41
ADDR_START = r",\s*(?=\d|Case|Squares?\b|including|vicinity|all properties|federal|parts of)"


def addr_key(s) -> str:
    """'1518 K Street, NW' -> '1518 k'; '' unless the text starts with a house number."""
    # "1132, 1140, and 1146 3rd Street" -> "1132 3": skip the rest of a house-number list.
    m = re.match(r"\s*(\d+)[-\d]*(?:,?\s*(?:and\s+)?\d+[-\d]*(?=[,\s]))*,?\s+(?:(\d+)(?:st|nd|rd|th)?|([A-Za-z]+))", str(s or ""))
    return f"{m.group(1)} {(m.group(2) or m.group(3)).lower()}" if m else ""


def fy(date) -> int | None:
    if pd.isna(date):
        return None
    d = pd.Timestamp(date)
    return d.year + 1 if d.month >= 10 else d.year


def records() -> pd.DataFrame:
    recs = []
    acts = pd.read_csv(NORMALIZED / "hprb_designation_actions.csv", parse_dates=["meeting_date"])
    for r in acts.itertuples():
        name, rest = (re.split(ADDR_START, r.header, maxsplit=1) + [""])[:2]
        if re.fullmatch(r"\d[\d-]*", name.strip()):  # "917, 919 and 921 6th Street NW, Case 20-12": all address
            rest = f"{name}, {rest}"
            name = re.sub(r",?\s*Case.*$", "", rest).strip()
        name = re.sub(r"^(?:[A-Z0-9]+\.|•)\s+", "", name).strip()
        # "It was announced that consideration of the proposed Kingman Park Historic District (Case 16-19, ..."
        name = re.sub(r"^(?:.*\bthe )?[Pp]roposed (.+?Historic District)\b.*$", r"\1", name)
        if re.search(r"\bamendment\b", r.header, re.I) and not re.search(r"\bamend", name, re.I):
            name += " (amendment)"  # e.g. "All Souls Church, Unitarian, ..., Case 20-10 (amendment)"; read by kind()
        outcome = "amended" if re.search(r"\bamend", name, re.I) and r.outcome == "designated" else r.outcome
        address = re.sub(r",?\s*Case.*$", "", rest).strip() or (name if name[:1].isdigit() else "")
        recs.append({"source": "hprb", "case_no": r.case_no, "name": name, "address": address, "date": r.meeting_date,
                     "outcome": outcome, "vote": f"{r.vote_for:.0f}-{r.vote_against:.0f}" if pd.notna(r.vote_for) else "",
                     "staff_recommendation": r.staff_recommendation, "nominated_by": "", "ref": r.source_file})
    upd = pd.read_csv(NORMALIZED / "inventory_update_items.csv")
    upd = upd[upd["designated"].notna()]
    for r in upd.itertuples():
        recs.append({"source": "update", "case_no": "", "name": r.name, "address": r.address if isinstance(r.address, str) else "",
                     "date": pd.to_datetime(r.designated, format=DATE_FMT, errors="coerce"),
                     "outcome": "amended" if "designation amended" in str(r.attribution) else "designated",
                     "nominated_by": r.nominated_by if isinstance(r.nominated_by, str) else "", "ref": f"{r.source_doc} p{r.page}"})
    man = pd.read_csv(INPUTS / "manual_designations.csv", parse_dates=["designated"])
    for r in man.itertuples():
        recs.append({"source": "manual", "case_no": "", "name": r.name, "address": r.address if isinstance(r.address, str) else "",
                     "date": r.designated, "outcome": "designated", "nominated_by": r.nominated_by if isinstance(r.nominated_by, str) else "",
                     "ref": f"{r.source_doc} p{r.source_page}"})
    inv = pd.read_csv(NORMALIZED / "inventory_2009_entries.csv")
    for r in inv.itertuples():
        first = (r.dc_designation if isinstance(r.dc_designation, str) and r.dc_designation else
                 r.dc_listing if isinstance(r.dc_listing, str) else "")
        date = pd.to_datetime(first.split("; ")[0], format=DATE_FMT, errors="coerce") if first else pd.NaT
        if pd.isna(date):
            continue
        recs.append({"source": "inventory", "case_no": "", "name": r.name, "address": str(r.text)[:80],
                     "date": date, "outcome": "designated", "nominated_by": "", "ref": f"inventory_2009 p{r.page}"})
    rep = pd.read_csv(INPUTS / "report_outcomes.csv")
    for r in rep.itertuples():
        recs.append({"source": "report", "case_no": "", "name": r.name, "address": r.address if isinstance(r.address, str) else "",
                     "date": pd.Timestamp(year=int(r.fy) - 1, month=10, day=1), "fy_only": True, "outcome": r.outcome,
                     "nominated_by": "", "ref": f"{r.source_doc} p{r.source_page}"})
    dp = NORMALIZED / "dcpl_pending_nominations.csv"
    if dp.exists():
        for r in pd.read_csv(dp).itertuples():
            recs.append({"source": "dcpl", "case_no": "", "name": r.name, "address": r.address if isinstance(r.address, str) else "",
                         "date": pd.NaT, "outcome": "pending", "nominated_by": "DC Preservation League", "ref": r.nomination_pdf})
    hp = NORMALIZED / "hpo_pending_nominations.csv"
    if hp.exists():
        for r in pd.read_csv(hp).itertuples():
            recs.append({"source": "hpo_pending", "case_no": r.case_no, "name": r.name,
                         "address": r.address if isinstance(r.address, str) else "", "date": pd.NaT,
                         "outcome": "pending", "nominated_by": "", "ref": "hpo_pending_nominations.html"})
    recs += unheard()
    df = pd.DataFrame(recs)
    df["key"] = df["name"].map(norm)
    df["alt"] = df["name"].map(aliases)
    df["addr"] = df["address"].map(addr_key)
    df["link"] = links(df)
    return df


def unheard() -> list[dict]:
    """Nominations HPO noticed for a hearing that HPRB never acted on; quotes checked against the notice."""
    from historic_preservation.normalize.hprb import source_text

    out = []
    for r in pd.read_csv(INPUTS / "unheard_nominations.csv", dtype=str).fillna("").itertuples():
        if re.sub(r"\s+", " ", r.quote) not in source_text(r.source_file, snapshot_dir() / "hprb"):
            raise ValueError(f"unheard_nominations.csv: quote not found in {r.source_file}: {r.quote[:60]!r}")
        out.append({"source": "notice", "case_no": r.case_no, "name": r.name, "address": r.address,
                    "date": pd.to_datetime(r.date) if r.date else pd.NaT, "outcome": r.outcome,
                    "nominated_by": "", "ref": r.source_file})
    return out


def links(df: pd.DataFrame) -> pd.Series:
    """Hand-reviewed links (inputs/nomination_links.csv) for records the matcher can't pair."""
    out = pd.Series("", index=df.index)
    for r in pd.read_csv(INPUTS / "nomination_links.csv", dtype=str).fillna("").itertuples():
        hit = (df["source"] == r.source) & (df["case_no"] == r.case_no if r.case_no else True) & (df["name"] == r.name if r.name else True)
        if not hit.any():
            raise ValueError(f"nomination_links.csv: no {r.source} record for {r.case_no or r.name!r}")
        out[hit] = r.link_id
    return out


def filer_review() -> dict[str, str]:
    """Applicants named in HPO staff reports (inputs/filer_review.csv), for cases no other source attributes.

    Each quote must appear in its staff report or nomination PDF from the HPRB crawl.
    """
    import subprocess
    review = pd.read_csv(INPUTS / "filer_review.csv", dtype=str)
    attachments = snapshot_dir() / "hprb" / "attachments"
    for r in review.itertuples():
        text = subprocess.run(["pdftotext", str(attachments / r.source_file), "-"], capture_output=True, text=True).stdout
        if re.sub(r"\s+", " ", r.quote) not in re.sub(r"\s+", " ", text):
            raise ValueError(f"filer_review.csv: quote not found in {r.source_file}: {r.quote[:60]!r}")
    return dict(zip(review["case_no"], review["nominated_by"]))


def _case_year(case_no: str) -> int | None:
    return 2000 + int(case_no[:2]) if case_no and int(case_no[:2]) < 50 else (1900 + int(case_no[:2]) if case_no else None)


def _numbers(key: str) -> set[str]:
    return set(re.findall(r"\b\d+\b", key))


def _score(a, b) -> float:
    pairs = [(a.key, b.key)] + [(x, y) for x, y in ((a.alt, b.key), (a.key, b.alt)) if len(x) >= 6 and len(y) >= 6]
    return max(fuzz.token_set_ratio(x, y) for x, y in pairs)


def _same(a, b) -> bool:
    score = _score(a, b)
    same_addr = bool(a.addr) and a.addr == b.addr
    if a.case_no and b.case_no:
        # HPRB action lists occasionally print one case number for two properties
        # (e.g. #10-04 for both The Flagler and Milton Hall), so names must also fit.
        generic = any(len(k) < 6 or k.startswith("case") for k in (a.key, b.key))
        return a.case_no == b.case_no and (score >= ADDR_MIN_SCORE or same_addr or generic)
    na, nb = _numbers(a.key), _numbers(b.key)
    if na and nb and not (na <= nb or nb <= na):
        return False  # Engine Company No. 22 vs No. 26
    # Same street address needs both records dated and a loosely similar name: HPO's
    # reports sometimes print a neighbouring item's address (Cotton Annex / Young-Browne).
    by_addr = same_addr and pd.notna(a.date) and pd.notna(b.date) and score >= ADDR_MIN_SCORE
    if not by_addr and (score < 90 or min(len(a.key), len(b.key)) < 6):
        return False
    # A numbered case can't be an earlier, dated record (e.g. a 2009 Inventory entry vs case 26-12).
    for x, y in ((a, b), (b, a)):
        if x.case_no and pd.notna(y.date) and pd.Timestamp(y.date).year < _case_year(x.case_no) - 1:
            return False
    if pd.isna(a.date) or pd.isna(b.date):
        return True
    window = 400 if (a.get("fy_only") is True or b.get("fy_only") is True) else 120
    return abs((pd.Timestamp(a.date) - pd.Timestamp(b.date)).days) <= window


SOURCE_ORDER = ["hprb", "hpo_pending", "notice", "update", "manual", "report", "dcpl", "inventory"]


def reconcile(df: pd.DataFrame) -> pd.DataFrame:
    # Numbered cases first, so undated records attach to the right case before older entries.
    df = df.assign(_o=df["source"].map(SOURCE_ORDER.index)).sort_values(["_o", "date"], kind="stable").drop(columns="_o")
    groups: list[list[int]] = []
    for i, a in df.iterrows():
        linked = next((g for g in groups if a.link and a.link in {df.loc[j, "link"] for j in g}), None)
        if linked is not None:
            linked.append(i)
            continue
        for g in groups:
            # Entries in one list (Inventory, an update, DCPL's or HPO's pending list) are distinct
            # by construction; only HPRB repeats a case across meetings.
            if a.source != "hprb" and any(df.loc[j, "source"] == a.source for j in g):
                continue
            cases = {df.loc[j, "case_no"] for j in g} - {""}
            if a.case_no and cases and a.case_no not in cases:
                continue  # never merge different case numbers
            # Group-level date check: a numbered case can't absorb records dated well before it.
            years = [pd.Timestamp(df.loc[j, "date"]).year for j in g if pd.notna(df.loc[j, "date"])]
            case_years = [_case_year(c) for c in cases | ({a.case_no} if a.case_no else set())]
            own_year = [pd.Timestamp(a.date).year] if pd.notna(a.date) else []
            if case_years and any(y < min(case_years) - 1 for y in years + own_year):
                continue
            if any(_same(a, df.loc[j]) for j in g):
                g.append(i)
                break
        else:
            groups.append([i])
    rules = load_rules()
    reviewed = filer_review()
    rows = []
    for n, g in enumerate(groups):
        sub = df.loc[g]
        best = sub.loc[sub["outcome"].map(OUTCOME_RANK).fillna(0).idxmax()]
        same = sub[sub["outcome"] == best["outcome"]]
        # The board's own record of its vote wins over a later report's date.
        dated = (same[same["source"] == "hprb"] if (same["source"] == "hprb").any() else same)["date"].dropna()
        exact = same[same.get("fy_only", pd.Series(False, index=same.index)).ne(True)].dropna(subset=["date"])
        conflict = (exact["date"].max() - exact["date"].min()).days > 120 if len(exact) > 1 else False
        nominators = [x for x in sub["nominated_by"] if isinstance(x, str) and x]
        case = next((c for c in sub["case_no"] if c), "")
        if not nominators and case in reviewed:
            nominators = [reviewed[case]]
        filer = classify(nominators[0], rules) if nominators else classify("", rules)
        rows.append({
            "nomination_id": f"N{n:05d}",
            "case_no": next((c for c in sub["case_no"] if c), ""),
            "name": sub.sort_values("source").iloc[0]["name"],
            "address": next((a for a in sub["address"] if isinstance(a, str) and a and a[0].isdigit()), ""),
            "outcome": best["outcome"],
            "outcome_date": dated.max() if len(dated) else pd.NaT,
            "fy": fy(dated.max()) if len(dated) else None,
            "first_seen": sub["date"].min(),
            "date_conflict": "; ".join(f"{s}:{d:%Y-%m-%d}" for s, d in zip(exact["source"], exact["date"])) if conflict else "",
            "vote": next((v for v in sub.get("vote", []) if isinstance(v, str) and v), ""),
            "staff_recommendation": next((s for s in sub.get("staff_recommendation", []) if isinstance(s, str) and s), ""),
            "nominated_by_raw": nominators[0] if nominators else "",
            **{k: filer[k] for k in ("filer_type", "filers", "co_filers")},
            "filer_inferred": bool(nominators),
            "seen_in": "; ".join(sorted(set(sub["source"]))),
            "n_sources": sub["source"].nunique(),
            "refs": "; ".join(sorted(set(str(x) for x in sub["ref"] if isinstance(x, str) and x))),
        })
    return pd.DataFrame(rows)


def split_neighborhood(noms: pd.DataFrame) -> pd.DataFrame:
    """Resolve 'neighborhood' filers: >= 2 nominations by the same group in the dataset -> society."""
    n = noms.copy()
    counts = n.loc[n["filer_type"] == "neighborhood", "filers"].str.split("; ").str[0].value_counts()
    is_nb = n["filer_type"] == "neighborhood"
    first = n.loc[is_nb, "filers"].str.split("; ").str[0]
    n.loc[is_nb, "filer_type"] = first.map(lambda g: "neighborhood_society" if counts.get(g, 0) >= 2 else "neighborhood_adhoc")
    n["filer_type_rule"] = ""
    n.loc[is_nb, "filer_type_rule"] = "society if the group has >= 2 nominations in this dataset (inferred)"
    return n


def kind(name: str) -> str:
    n = str(name).lower()
    if re.search(r"multiple[- ]property|thematic document", n):
        return "thematic_document"  # a National Register framework, not a designation
    if re.search(r"historic district|\bhd\b", n):
        return "district_amendment" if re.search(r"expan|amend|boundar", n) else "district"
    return "landmark_amendment" if re.search(r"\bamend|additional documentation", n) else "landmark"


def expected_missing(row) -> str:
    """Sources that cover this row's year and outcome but don't include it (for review)."""
    seen = set(row["seen_in"].split("; "))
    missing = []
    if row["outcome"] == "designated" and pd.notna(row["fy"]):
        if 2010 <= row["fy"] <= 2022 and not seen & {"update", "manual"}:
            missing.append("update")
        if row["fy"] >= 2007 and "hprb" not in seen:
            missing.append("hprb")
    return "; ".join(missing)


def run() -> None:
    noms = split_neighborhood(reconcile(records()))
    noms.insert(3, "kind", noms["name"].map(kind))
    noms["expected_missing"] = noms.apply(expected_missing, axis=1)
    noms.to_csv(JOINED / "nominations.csv", index=False, date_format="%Y-%m-%d")
    review = noms[(noms["expected_missing"] != "") | (noms["date_conflict"] != "")].copy()
    # Hand-checked explanations (inputs/reconciliation_notes.csv); rows without one still need review.
    notes = pd.read_csv(INPUTS / "reconciliation_notes.csv").set_index("name")["note"]
    stale = set(notes.index) - set(review["name"])
    if stale:
        raise ValueError(f"reconciliation_notes.csv: no longer in reconciliation.csv: {sorted(stale)}")
    review["review_note"] = review["name"].map(notes).fillna("")
    review.to_csv(JOINED / "reconciliation.csv", index=False, date_format="%Y-%m-%d")
    print(f"nominations: {len(noms)} rows; {len(review)} in reconciliation.csv, "
          f"{(review['review_note'] == '').sum()} without a review note")
