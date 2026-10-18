"""H6 (secondary evidence): appeals of Mayor's Agent permit decisions to the DC Court of Appeals.

Only decisions someone appealed reach the court, so these are not Mayor's
Agent approval rates; they show how the court treats the override when it is
challenged, and how long an appeal adds. The primary H6 source is the
Georgetown Law collection of Mayor's Agent decisions (manual fetch).
"""

import json

import pandas as pd

from historic_preservation.config import ANALYSIS, NORMALIZED

OWNER = {"owner"}


def run() -> None:
    path = NORMALIZED / "court_cases.csv"
    if not path.exists():
        return
    c = pd.read_csv(path)
    ma = c[c["decision_reviewed"] == "mayors_agent_permit"].copy()
    ma["appellant"] = ma["petitioner_type"].map(lambda t: "owner" if t in OWNER else "preservation or neighborhood side")
    table = pd.crosstab([ma["appellant"], ma["agency_ruling"].str.split().str[0]], ma["preservation_side"])
    table.to_csv(ANALYSIS / "court_mayors_agent_appeals.csv")
    lag = ma["days_order_to_opinion"].dropna()
    unfetched = pd.read_csv(NORMALIZED / "court_opinions.csv").query("not text_fetched")["case_name"].tolist()
    summary = {
        "mayors_agent_appeals": int(len(ma)),
        "by_appellant": ma["appellant"].value_counts().to_dict(),
        "preservation_side_outcome": ma["preservation_side"].value_counts().to_dict(),
        "owner_appeals_preservation_side_prevailed": int(((ma["appellant"] == "owner") & (ma["preservation_side"] == "prevailed")).sum()),
        "days_order_to_opinion": {"n": int(len(lag)), "median": float(lag.median()), "min": int(lag.min()), "max": int(lag.max())},
        "designation_challenges": c[c["decision_reviewed"] == "designation"][["decided", "case_label", "preservation_side"]].to_dict("records"),
        "opinions_not_fetched": unfetched,
        "caveat": "Appealed cases only; not a sample of all Mayor's Agent decisions.",
    }
    (ANALYSIS / "court_appeals_summary.json").write_text(json.dumps(summary, indent=1, default=str))
