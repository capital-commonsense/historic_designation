"""HPO's permit and concept reviews by type of application, and how many went to HPRB and the Mayor's Agent.

inputs/hpo_review_types.csv transcribes the "Permit and Concept Reviews by Type" table in each HPO
annual report, FY2018-23: per type, all applications, those referred to HPRB, and those that went
to the Mayor's Agent, plus the table's printed TOTAL row. Each row's quote is the table row as
pdftotext -raw prints it, and its numbers must match the columns. The stages are counts per year,
not tracked cases: a Mayor's Agent case need not have gone through HPRB that year (FY2019 has more
demolitions at the Mayor's Agent than at HPRB).
"""

import json
import re

import pandas as pd

from historic_preservation.analysis.grants import report_text
from historic_preservation.config import ANALYSIS, INPUTS

TYPES = ("alteration_addition", "new_construction", "demolition", "subdivision", "other")
STAGES = ("all", "hprb", "mayors_agent")


def table() -> pd.DataFrame:
    r = pd.read_csv(INPUTS / "hpo_review_types.csv").fillna({"note": ""})
    bad = set(r["type"]) - set(TYPES) - {"total"}
    if bad:
        raise ValueError(f"hpo_review_types.csv: unknown types {bad}")
    texts = {d: report_text(d) for d in r["source_doc"].unique()}
    for x in r.itertuples():
        if x.quote not in texts[x.source_doc]:
            raise ValueError(f"hpo_review_types.csv: {x.fy} {x.type}: not found in {x.source_doc}: {x.quote!r}")
        printed = [int(n.replace(",", "")) for n in re.findall(r"(?<![\d(.])\d[\d,]*(?![\d%.])", re.sub(r"^TOTAL FY \d{4}", "", x.quote))]
        if printed != [getattr(x, s) for s in STAGES][:len(printed)]:
            raise ValueError(f"hpo_review_types.csv: {x.fy} {x.type}: columns differ from the quote {x.quote!r}")
    return r


def run() -> None:
    r = table()
    rows, total = r[r["type"] != "total"], r[r["type"] == "total"].set_index("fy")
    sums = rows.groupby("fy")[list(STAGES)].sum()
    off = {int(fy): {s: [int(sums.loc[fy, s]), int(total.loc[fy, s])] for s in STAGES if sums.loc[fy, s] != total.loc[fy, s]}
           for fy in sums.index}
    rows[["fy", "type", *STAGES]].to_csv(ANALYSIS / "hpo_review_types.csv", index=False)
    by_type = rows.groupby("type")[list(STAGES)].sum()
    s = {
        "years": [int(sums.index.min()), int(sums.index.max())],
        "printed_totals": {st: int(total[st].sum()) for st in STAGES},
        "row_sums": {st: int(sums[st].sum()) for st in STAGES},
        "by_type": {t: {st: int(by_type.loc[t, st]) for st in STAGES} for t in TYPES},
        "rows_differ_from_printed_total": {fy: v for fy, v in off.items() if v},
    }
    (ANALYSIS / "hpo_review_types_summary.json").write_text(json.dumps(s, indent=2))
    p = s["printed_totals"]
    print(f"review types: FY{s['years'][0]}-{s['years'][1]} {p['all']:,} applications, {p['hprb']} to HPRB, "
          f"{p['mayors_agent']} to the Mayor's Agent; rows differ from printed totals in {sorted(s['rows_differ_from_printed_total']) or 'no year'}")
