"""Compare HPO's case log (normalize/case_log.py) with nominations.csv, case by case -> case_log_comparison.csv.

Review only: nothing here changes nominations.csv. Each case number in either table gets one status:
  agree            same outcome, dates within 120 days (or the log gives no date)
  date_differs     same outcome, dates further apart
  outcome_differs  different outcomes
  log_only         in the log, not in nominations.csv
  scrape_only      a case number in nominations.csv the log doesn't list
  not_comparable   log actions with no counterpart here (superseded, forwarded to the National Register)
  reviewed         different outcomes, decided by hand in inputs/case_log_review.csv
Outcomes are compared in families: designated, amended, adopted and the log's "1964 listing updated" are one.
Case numbers that match but whose names don't (token_set_ratio < 60) are flagged `name_check`.
"""

import pandas as pd
from rapidfuzz import fuzz

from historic_preservation.config import JOINED, NORMALIZED

FAMILY = {"designated": "designated", "amended": "designated", "adopted": "designated", "updated": "designated",
          "denied": "denied", "withdrawn": "withdrawn", "revoked": "revoked", "de-designated": "revoked",
          "continued": "open", "none": "open", "pending": "open", "not_heard": "open"}
NOT_COMPARABLE = {"superseded", "forwarded", "listed"}
DAYS = 120


def status(r) -> str:
    if pd.isna(r["nomination_id"]):
        return "log_only"
    if pd.isna(r["action"]):
        return "scrape_only"
    if r["action"] in NOT_COMPARABLE:
        return "not_comparable"
    if FAMILY.get(r["action"]) != FAMILY.get(r["outcome"]):
        return "reviewed" if pd.notna(r["outcome_note"]) else "outcome_differs"
    if pd.notna(r["days_apart"]) and abs(r["days_apart"]) > DAYS:
        return "date_differs"
    return "agree"


def compare(log: pd.DataFrame, noms: pd.DataFrame) -> pd.DataFrame:
    log = log[(log["case_no"] != "") & (log["name"] != "VOID")]
    # A row can carry several case numbers (one designation filed twice); compare each.
    noms = (noms.assign(case_no=noms["case_nos"].fillna("").str.split("; ")).explode("case_no")
            .query("case_no != ''").drop_duplicates("case_no"))
    m = log.merge(noms[["case_no", "nomination_id", "name", "outcome", "outcome_date", "seen_in", "outcome_note"]],
                  on="case_no", how="outer", suffixes=("_log", "_scrape"))
    m["days_apart"] = (pd.to_datetime(m["action_date"]) - pd.to_datetime(m["outcome_date"])).dt.days
    m["status"] = m.apply(status, axis=1)
    both = m["name_log"].notna() & m["name_scrape"].notna()
    m["name_check"] = both & pd.Series([fuzz.token_set_ratio(str(a).lower(), str(b).lower()) < 60
                                        for a, b in zip(m["name_log"], m["name_scrape"])], index=m.index)
    cols = ["case_no", "status", "name_check", "name_log", "name_scrape", "action", "outcome", "action_date",
            "date_precision", "outcome_date", "days_apart", "action_raw", "nomination_id", "seen_in", "outcome_note", "line"]
    return m[cols].sort_values(["status", "case_no"])


def run() -> None:
    path = NORMALIZED / "hpo_case_log.csv"
    if not path.exists():
        return
    log = pd.read_csv(path, dtype={"case_no": str}, keep_default_na=False, na_values=[""])
    log["case_no"] = log["case_no"].fillna("")
    noms = pd.read_csv(JOINED / "nominations.csv", dtype={"case_no": str, "case_nos": str})
    out = compare(log, noms)
    out.to_csv(JOINED / "case_log_comparison.csv", index=False, date_format="%Y-%m-%d")
    print("case log vs nominations.csv:\n" + out["status"].value_counts().to_string()
          + f"\n  names to check: {int(out['name_check'].sum())}")
