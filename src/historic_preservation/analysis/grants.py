"""The Historic Homeowner Grant program HPO runs: applicants, awards and spending by fiscal year.

inputs/homeowner_grants.csv holds one figure per row, read from HPO's annual reports (FY2007-23)
with the words or table row it came from; `chart label` rows are numbers printed on a report's bar
chart (available funds and awards in $ thousands, projects per year). Each quote or label is checked
against the report's text. Where reports disagree about a year, the row takes the year's own report
and notes the other figure; HPO's later bar charts revise several years' spending.
"""

import json
import re
import subprocess

import pandas as pd

from historic_preservation.config import ANALYSIS, INPUTS, snapshot_dir

MEASURES = ("applicants", "awarded_count", "awarded_dollars", "available", "expended", "projects", "no_new_round")


def report_text(doc: str) -> str:
    """Text in content order (-raw), which keeps the reports' sidebars and tables from interleaving."""
    path = snapshot_dir() / "documents" / f"{doc}.pdf"
    return re.sub(r"\s+", " ", subprocess.run(["pdftotext", "-raw", str(path), "-"], capture_output=True, text=True).stdout)


def table() -> pd.DataFrame:
    g = pd.read_csv(INPUTS / "homeowner_grants.csv", dtype={"quote": str}).fillna({"quote": "", "note": ""})
    bad = set(g["measure"]) - set(MEASURES)
    if bad:
        raise ValueError(f"homeowner_grants.csv: unknown measures {bad}")
    if g.duplicated(["fy", "measure"]).any():
        raise ValueError(f"homeowner_grants.csv: repeated rows {g[g.duplicated(['fy', 'measure'])][['fy', 'measure']].values.tolist()}")
    texts = {d: report_text(d) for d in g["source_doc"].unique()}
    for r in g.itertuples():
        q = re.sub(r"\s+", " ", r.quote)
        found = (re.search(rf"(?<![\d,.$]){re.escape(q)}(?![\d,])", texts[r.source_doc]) if r.method == "chart label"
                 else q in texts[r.source_doc])
        if not q or not found:
            raise ValueError(f"homeowner_grants.csv: {r.fy} {r.measure}: not found in {r.source_doc}: {q[:60]!r}")
    return g.pivot(index="fy", columns="measure", values="value").reindex(columns=MEASURES)


def run() -> None:
    t = table()
    t.to_csv(ANALYSIS / "homeowner_grants_by_year.csv")
    both = t.dropna(subset=["available", "expended"])
    s = {
        "years": [int(t.index.min()), int(t.index.max())],
        "expended_total": float(t["expended"].sum()),
        "expended_years": [int(t["expended"].first_valid_index()), int(t["expended"].last_valid_index())],
        "no_new_round": [int(y) for y in t.index[t["no_new_round"] == 1]],
        "available_window": [int(both.index.min()), int(both.index.max())],
        "available_total": float(both["available"].sum()),
        "awarded_total_window": float(both["awarded_dollars"].sum()),
        "expended_total_window": float(both["expended"].sum()),
        "awards_total": float(t["awarded_count"].sum()),
        "applicants_total": float(t["applicants"].sum()),
        "note": "Figures as HPO's annual reports state them; see inputs/homeowner_grants.csv for revisions and sources.",
    }
    (ANALYSIS / "homeowner_grants_summary.json").write_text(json.dumps(s, indent=2))
    print(f"grants: HPO homeowner grants spent ${s['expended_total'] / 1e6:.2f}M, FY{s['expended_years'][0]}-"
          f"{s['expended_years'][1]}; FY{s['available_window'][0]}-{s['available_window'][1]}: "
          f"${s['available_total'] / 1e6:.2f}M available, ${s['awarded_total_window'] / 1e6:.2f}M awarded, "
          f"${s['expended_total_window'] / 1e6:.2f}M spent")
