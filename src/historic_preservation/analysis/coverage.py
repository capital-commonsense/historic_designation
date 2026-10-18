"""Coverage of the scraped nominations against HPO's published counts, by fiscal year.

HPO's "Historic Landmark Designations" table counts landmark applications by
year received, and approvals/denials by year decided. Scraped cases are dated
by decision (or designation), so `coverage_ratio` (scraped_cases / hpo_received,
as first defined) mixes the two; `approved_coverage` compares like with
like. Any rate for a year with coverage_ratio below 0.8 must say so.

HPO counts are taken from the latest edition that prints each year; the
number of editions and whether they disagree are reported alongside.
"""

import pandas as pd

from historic_preservation.config import ANALYSIS, JOINED, NORMALIZED

HPO_COLS = ["received", "approved", "approved_owner_opposed", "denied", "denied_owner_opposed"]
THRESHOLD = 0.8


def hpo_counts() -> pd.DataFrame:
    t = pd.read_csv(NORMALIZED / "hpo_landmark_table_rows.csv")
    t = t[t["layout"].str.startswith("R A", na=False) & (t["fy"] != "TOTAL")].copy()
    t["fy"] = t["fy"].astype(int)
    t["edition"] = t["source_doc"].str.extract(r"fy(\d{4})").astype(int)
    for c in HPO_COLS:
        t[c] = pd.to_numeric(t[c], errors="coerce")
    latest = t.sort_values("edition").groupby("fy").last()[HPO_COLS + ["source_doc"]]
    latest.columns = [f"hpo_{c}" for c in HPO_COLS] + ["hpo_source"]
    latest["hpo_editions"] = t.groupby("fy").size()
    latest["hpo_editions_disagree"] = t.groupby("fy")[HPO_COLS].nunique().max(axis=1) > 1
    return latest


def scraped_counts(noms: pd.DataFrame) -> pd.DataFrame:
    lm = noms[noms["kind"].str.startswith("landmark") & noms["fy"].notna()].copy()
    lm["fy"] = lm["fy"].astype(int)
    g = lm.groupby("fy")
    out = pd.DataFrame({
        "scraped_cases": g.size(),
        "scraped_approved": g["outcome"].apply(lambda s: (s == "designated").sum()),
        "scraped_denied": g["outcome"].apply(lambda s: (s == "denied").sum()),
        "scraped_withdrawn": g["outcome"].apply(lambda s: (s == "withdrawn").sum()),
        "scraped_pending": g["outcome"].apply(lambda s: s.isin(["pending", "continued"]).sum()),
        "filer_known_share": g["filer_type"].apply(lambda s: (s != "unknown").mean()),
    })
    return out


def table() -> pd.DataFrame:
    noms = pd.read_csv(JOINED / "nominations.csv")
    hpo, scraped = hpo_counts(), scraped_counts(noms)
    designated = noms[noms["outcome"] == "designated"].dropna(subset=["fy"])
    additions = designated.groupby(designated["fy"].astype(int)).size().rename("inventory_additions")
    cov = hpo.join(scraped, how="outer").join(additions, how="left")
    cov["coverage_ratio"] = cov["scraped_cases"] / cov["hpo_received"]
    cov["approved_coverage"] = cov["scraped_approved"] / cov["hpo_approved"]
    cov["adequate"] = cov["coverage_ratio"] >= THRESHOLD
    cov["records_request_cases"] = pd.NA
    cov.index.name = "fy"
    return cov.sort_index()


def run() -> None:
    cov = table()
    cov.to_csv(ANALYSIS / "coverage_by_year.csv")
    print(f"coverage: {int(cov['adequate'].sum())} of {cov['hpo_received'].notna().sum()} HPO-reported years at >= {THRESHOLD}")
