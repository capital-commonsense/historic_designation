"""H7: how often HPRB departs from the HPO staff recommendation on a nomination, and which way.

inputs/hprb_staff_review.csv holds one HPO staff report per case: its recommendation on the
application (`grant`, `deny`, or `none` stated), read from the report with a checked quote.
HPRB's decision is the nomination's final outcome in nominations.csv. Staff reports come from
the planning.dc.gov crawl, which posts them mostly from FY2014 on.
"""

import json
import re

import pandas as pd

from historic_preservation.config import ANALYSIS, INPUTS, JOINED, snapshot_dir
from historic_preservation.normalize.hprb import doc_text

GRANTED = {"designated", "amended", "de-designated"}  # Yellow Tavern: the application was to revoke
DECIDED = GRANTED | {"denied"}


def report_text(name: str) -> str:
    t = re.sub(r"\s+", " ", doc_text(snapshot_dir() / "hprb" / "attachments" / name))
    return re.sub(r"\b([DUSNWE])\.(?=[A-Z]\.?)", r"\1", t)  # 'D.C.' -> 'DC', as the quotes are written


def review() -> pd.DataFrame:
    r = pd.read_csv(INPUTS / "hprb_staff_review.csv", dtype=str).fillna("")
    if r["case_no"].duplicated().any():
        raise ValueError(f"hprb_staff_review.csv: repeated cases {sorted(r.loc[r['case_no'].duplicated(), 'case_no'])}")
    bad = set(r["position"]) - {"grant", "deny", "none"}
    if bad:
        raise ValueError(f"hprb_staff_review.csv: unknown positions {bad}")
    for x in r.itertuples():
        if x.quote and x.quote not in report_text(x.source_file):
            raise ValueError(f"hprb_staff_review.csv: quote not found in {x.source_file}: {x.quote[:60]!r}")
    return r


def run() -> None:
    if not (INPUTS / "hprb_staff_review.csv").exists():
        return
    n = pd.read_csv(JOINED / "nominations.csv", dtype=str).dropna(subset=["case_no"]).drop_duplicates("case_no")
    d = review().merge(n[["case_no", "name", "kind", "outcome", "fy"]], on="case_no", how="left")
    d["board"] = d["outcome"].map(lambda o: "grant" if o in GRANTED else "deny" if o == "denied" else None)
    d["departure"] = d["board"].notna() & d["position"].isin(["grant", "deny"]) & (d["board"] != d["position"])
    d.to_csv(ANALYSIS / "h7_staff_vs_board.csv", index=False)
    scored = d[d["board"].notna() & d["position"].isin(["grant", "deny"])]
    dep = scored[scored["departure"]]
    summary = {
        "reports": int(len(d)),
        "not_in_nominations": sorted(d.loc[d["outcome"].isna(), "case_no"]),
        "decided_with_position": int(len(scored)),
        "staff_grant": int((scored["position"] == "grant").sum()),
        "staff_deny": int((scored["position"] == "deny").sum()),
        "departures": int(len(dep)),
        "board_denied_staff_grant": dep.loc[dep["position"] == "grant", ["case_no", "name"]].to_dict("records"),
        "board_granted_staff_deny": dep.loc[dep["position"] == "deny", ["case_no", "name"]].to_dict("records"),
        "staff_deny_followed": int(((scored["position"] == "deny") & ~scored["departure"]).sum()),
        "fiscal_years": [int(float(scored["fy"].dropna().min())), int(float(scored["fy"].dropna().max()))],
        "caveats": [
            "One staff report per case; where HPO revised its recommendation, the latest report is used (Barry Farm).",
            "Three crawled reports carry another case's number in their header and are excluded; the Hadley House report (header 15-15) is matched to Case 15-17 by name and address.",
            "Withdrawn, continued and pending nominations are not scored; partial designations (Barry Farm: 40 units of the complex) count as granted.",
        ],
    }
    (ANALYSIS / "h7_summary.json").write_text(json.dumps(summary, indent=1))
