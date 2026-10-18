"""H6: Mayor's Agent outcomes from the Georgetown Law collection.

Caveats carried into the summary: the collection is the library's effort to
be "as complete as possible", not a certified census; the basis flags come from
the library's subject tags; dispositions come from the library's descriptions
or, where those are silent, from the decision PDFs (inputs/mayors_agent_review.csv).
"""

import json

import pandas as pd

from historic_preservation.config import ANALYSIS, NORMALIZED

BASES = {"special_merit": "Special merit", "economic_hardship": "Economic hardship",
         "necessary_public_interest": "Necessary in the public interest",
         "consistent_with_purposes": "Consistent with the purposes of the Act"}
DECIDED = ("granted", "partial", "denied")


def load() -> pd.DataFrame:
    d = pd.read_csv(NORMALIZED / "mayors_agent_decisions.csv", parse_dates=["order_date"])
    d["decade"] = (d["order_date"].dt.year // 10 * 10).astype("Int64")
    return d


def rates(d: pd.DataFrame) -> dict:
    decided = d[d["disposition"].isin(DECIDED)]
    return {"decisions": int(len(d)), "decided_on_merits": int(len(decided)),
            "granted": int((decided["disposition"] == "granted").sum()),
            "partial": int((decided["disposition"] == "partial").sum()),
            "denied": int((decided["disposition"] == "denied").sum()),
            "granted_share": round(float((decided["disposition"] == "granted").mean()), 3) if len(decided) else None}


def timing(d: pd.DataFrame) -> dict:
    """Median and quartiles of hearing-to-order days and application-to-order fiscal years."""
    days = d["days_hearing_to_order"]
    ok = days[days >= 0]
    fy = d["fy_application_to_order"].dropna()
    q = lambda s, x: round(float(s.quantile(x)), 1) if len(s) else None
    return {"decisions": int(len(d)),
            "hearing_dated": int(days.notna().sum()), "hearing_after_order_excluded": int((days < 0).sum()),
            "days_hearing_to_order": {"n": int(len(ok)), "p25": q(ok, .25), "median": q(ok, .5), "p75": q(ok, .75),
                                      "over_180": int((ok > 180).sum()), "over_365": int((ok > 365).sum())},
            "fiscal_years_application_to_order": {"n": int(len(fy)), "median": q(fy, .5),
                                                  "same_fy": int((fy == 0).sum()), "next_fy": int((fy == 1).sum()),
                                                  "two_or_more": int((fy >= 2).sum())}}


def run() -> None:
    path = NORMALIZED / "mayors_agent_decisions.csv"
    if not path.exists():
        return
    d = load()
    table = pd.crosstab([d["decade"]], d["disposition"])
    table.to_csv(ANALYSIS / "mayors_agent_outcomes_by_decade.csv")
    summary = {
        "all": rates(d),
        "by_basis": {label: rates(d[d[col]]) for col, label in BASES.items()},
        "by_case_type": {t: rates(g) for t, g in d.groupby("case_type")},
        "case_type_source": d["case_type_source"].str.split(":").str[0].value_counts().to_dict(),
        "by_reviewer_position": {pos: rates(g) for pos, g in d.groupby("reviewer_position")},
        "by_case_type_and_reviewer_position": {f"{t} / {pos}": rates(g)
                                               for (t, pos), g in d.groupby(["case_type", "reviewer_position"])},
        "reviewing_body": d["reviewing_body"].replace("", "not stated").value_counts().to_dict(),
        "decisions_mentioning_dcpl": int(d["mentions_dcpl"].sum()),
        "timing": timing(d),
        "timing_by_case_type": {t: timing(g) for t, g in d.groupby("case_type")},
        "timing_by_decade": {str(k): timing(g) for k, g in d.groupby("decade")},
        "timing_by_disposition": {k: timing(g) for k, g in d.groupby("disposition")},
        "by_decade": {str(k): rates(g) for k, g in d.groupby("decade")},
        "years": [int(d["order_date"].dt.year.min()), int(d["order_date"].dt.year.max())],
        "disposition_source": d["disposition_source"].str.split(":").str[0].value_counts().to_dict(),
        "date_conflicts": int(d["date_conflict"].sum()),
        "untagged_by_library_by_decade": {str(k): int(v) for k, v in d[d["subjects"].isna()].groupby("decade").size().items()},
        "caveats": [
            "Georgetown Law's collection aims to be as complete as possible; it is not a certified census of decisions.",
            "Basis flags are the library's subject tags (a tag can mark an issue discussed, not only the ground claimed); for decisions the library left untagged, the grounds the applicant claimed, read from the decision (inputs/mayors_agent_basis_review.csv).",
            "Dispositions: library descriptions where stated, otherwise read from the decision PDF with a checked quote.",
            "Approvals with conditions count as granted; 'partial' is a split decision.",
            "Reviewer position is what HPRB (Joint Committee on Landmarks before 1983; Commission of Fine Arts in Georgetown) recommended on the application, read from each decision with a checked quote (inputs/mayors_agent_hprb_review.csv); 'no_position' covers referrals for a special-merit hearing.",
            "mentions_dcpl is a text mention of DC Preservation League or Don't Tear It Down, not proof that the group was a party.",
            "Timing: application year is the HPA number's fiscal-year prefix (earliest if several), so application-to-order is in whole fiscal years; reconsiderations and remands keep the original number and inflate it. Hearing-to-order runs from the last Mayor's Agent hearing session named in the decision (inputs/mayors_agent_hearing_dates.csv: found by pattern and spot-checked, or read by hand; quotes checked) to the order date; decisions whose catalog order date precedes the hearing are excluded.",
            "Case type is the primary permit sought (demolition > subdivision > new construction > alteration), from the library's permit type, tags and title, or read from the decision (inputs/mayors_agent_type_review.csv).",
        ],
    }
    (ANALYSIS / "mayors_agent_summary.json").write_text(json.dumps(summary, indent=1))
