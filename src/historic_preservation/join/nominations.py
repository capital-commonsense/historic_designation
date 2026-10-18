"""Reconcile nominations across sources into nominations.csv (+ reconciliation.csv).

There is no single docket. Each source contributes partial records:
  hprb       HPRB actions (case no., meeting date, outcome, vote)    c. 2008+
  update     Inventory updates / HPO reports (nominator, date)        FY2010+
  manual     hand-read rows (inputs/manual_designations.csv)
  inventory  2009 Inventory designation entries (date only)           to 2009
  report     outcomes named in annual reports (inputs/report_outcomes.csv)
  dcpl       DCPL's posted list of its pending nominations

Records are merged on case number when both have one, otherwise on name
similarity (token_set_ratio >= 90) within a date window. A merged row lists
every source it was seen in; rows seen in only one source are written to
reconciliation.csv for review. Outcomes from later actions win over earlier
ones for the same case (e.g. continued, then designated).
"""

import re

import pandas as pd
from rapidfuzz import fuzz

from historic_preservation.config import INPUTS, JOINED, NORMALIZED
from historic_preservation.normalize.filers import classify, load_rules

OUTCOME_RANK = {"designated": 5, "denied": 5, "withdrawn": 5, "de-designated": 6, "amended": 4,
                "pending": 1, "continued": 2, "unclear": 0}
DATE_FMT = "%B %d, %Y"


def norm(s) -> str:
    s = str(s or "").lower().replace("’", "'")
    s = re.sub(r"\(.*?\)|\[.*?\]", " ", s)
    s = re.sub(r"\b(the|and|of|historic|landmark|nomination)\b|[^a-z0-9 ]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def fy(date) -> int | None:
    if pd.isna(date):
        return None
    d = pd.Timestamp(date)
    return d.year + 1 if d.month >= 10 else d.year


def records() -> pd.DataFrame:
    recs = []
    acts = pd.read_csv(NORMALIZED / "hprb_designation_actions.csv", parse_dates=["meeting_date"])
    for r in acts.itertuples():
        name, _, rest = r.header.partition(",")
        recs.append({"source": "hprb", "case_no": r.case_no, "name": re.sub(r"^[A-Z0-9]+\.\s+", "", name).strip(),
                     "address": re.sub(r",?\s*Case.*$", "", rest).strip(), "date": r.meeting_date,
                     "outcome": r.outcome, "vote": f"{r.vote_for:.0f}-{r.vote_against:.0f}" if pd.notna(r.vote_for) else "",
                     "staff_recommendation": r.staff_recommendation, "nominated_by": "", "ref": r.source_file})
    upd = pd.read_csv(NORMALIZED / "inventory_update_items.csv")
    upd = upd[upd["designated"].notna()]
    for r in upd.itertuples():
        recs.append({"source": "update", "case_no": "", "name": r.name, "address": r.address if isinstance(r.address, str) else "",
                     "date": pd.to_datetime(r.designated, format=DATE_FMT, errors="coerce"), "outcome": "designated",
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
    df = pd.DataFrame(recs)
    df["key"] = df["name"].map(norm)
    return df


def _same(a, b) -> bool:
    if a.case_no and b.case_no:
        return a.case_no == b.case_no
    if fuzz.token_set_ratio(a.key, b.key) < 90 or min(len(a.key), len(b.key)) < 6:
        return False
    if pd.isna(a.date) or pd.isna(b.date):
        return True
    window = 400 if (a.get("fy_only") is True or b.get("fy_only") is True) else 120
    return abs((pd.Timestamp(a.date) - pd.Timestamp(b.date)).days) <= window


def reconcile(df: pd.DataFrame) -> pd.DataFrame:
    groups: list[list[int]] = []
    for i, a in df.iterrows():
        for g in groups:
            if any(_same(a, df.loc[j]) for j in g):
                g.append(i)
                break
        else:
            groups.append([i])
    rules = load_rules()
    rows = []
    for n, g in enumerate(groups):
        sub = df.loc[g]
        best = sub.loc[sub["outcome"].map(OUTCOME_RANK).fillna(0).idxmax()]
        dated = sub[sub["outcome"] == best["outcome"]]["date"].dropna()
        nominators = [x for x in sub["nominated_by"] if isinstance(x, str) and x]
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


def run() -> None:
    noms = split_neighborhood(reconcile(records()))
    noms.to_csv(JOINED / "nominations.csv", index=False, date_format="%Y-%m-%d")
    noms[noms["n_sources"] == 1].to_csv(JOINED / "reconciliation.csv", index=False, date_format="%Y-%m-%d")
    print(f"nominations: {len(noms)} rows; {int((noms['n_sources'] == 1).sum())} single-source rows to review")
