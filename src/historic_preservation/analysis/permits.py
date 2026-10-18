"""H2: are nominations filed while a raze or major alteration application is pending?

Two kinds of evidence, kept apart:
- documented: HPRB agendas, actions, HPO notices and staff reports that list a raze
  or alteration application alongside a pending nomination (inputs/h2_pending_applications.csv);
- permit timing: DOB open data showing a raze permit issued at a nominated address
  soon after the nomination was denied or withdrawn. The open data lists issued
  permits only (2009 on), with no application dates, so this suggests but does not
  show that the application was pending.

Both are lower bounds: agendas list a raze application only when HPO scheduled it
"if designated", and the nominations table rarely sees nominations withdrawn
before a hearing.
"""

import json

import pandas as pd

from historic_preservation.config import ANALYSIS, JOINED

KINDS = ("landmark", "landmark_amendment")
HEARD = ("designated", "denied", "withdrawn", "amended")
FY_FROM, FY_TO = 2007, 2025
TIMING_DAYS = 180


def fy(dates: pd.Series) -> pd.Series:
    d = pd.to_datetime(dates)
    return d.dt.year + (d.dt.month >= 10)


def heard(noms: pd.DataFrame) -> pd.DataFrame:
    """Individual-landmark nominations HPRB acted on, FY_FROM-FY_TO."""
    h = noms[noms["kind"].isin(KINDS) & noms["outcome"].isin(HEARD)
             & noms["seen_in"].str.contains("hprb", na=False)].copy()
    h["outcome_fy"] = fy(h["outcome_date"])
    return h[h["outcome_fy"].between(FY_FROM, FY_TO)]


def outcome_counts(df: pd.DataFrame) -> dict:
    c = df["outcome"].replace({"amended": "designated"}).value_counts()
    n = int(c.sum())
    return {"n": n, **{k: int(v) for k, v in c.items()},
            "designated_share": round(float(c.get("designated", 0) / n), 3) if n else None}


def timing(noms: pd.DataFrame, permits: pd.DataFrame) -> pd.DataFrame:
    """Raze permits issued at the address within TIMING_DAYS after a denial or withdrawal."""
    p = permits[permits["subtype"].eq("raze")].merge(
        noms[["nomination_id", "outcome_date"]], on="nomination_id")
    p["days_after_outcome"] = (pd.to_datetime(p["issued"]) - pd.to_datetime(p["outcome_date"])).dt.days
    p = p[p["outcome"].isin(["denied", "withdrawn"]) & p["days_after_outcome"].between(-30, TIMING_DAYS)]
    return p[["nomination_id", "case_no", "name", "outcome", "outcome_date", "permit_id", "issued",
              "days_after_outcome", "permit_address", "desc_of_work"]]


def run() -> None:
    path = JOINED / "h2_pending_applications.csv"
    if not path.exists():
        return
    noms = pd.read_csv(JOINED / "nominations.csv")
    pending = pd.read_csv(path, dtype={"case_no": str})
    permits = pd.read_csv(JOINED / "nomination_permits.csv", dtype={"case_no": str})
    h = heard(noms)

    raze_cases = set(pending.loc[pending["application_type"] == "raze", "case_no"])
    other_cases = set(pending.loc[pending["application_type"] != "raze", "case_no"]) - raze_cases
    h["pending"] = h["case_no"].map(lambda c: "raze" if c in raze_cases else "alteration_or_new" if c in other_cases else "none")

    t = timing(h, permits)
    t.to_csv(ANALYSIS / "h2_raze_after_denial.csv", index=False)
    t_only = t[~t["case_no"].isin(pending["case_no"])]
    denied_withdrawn_2009 = h[h["outcome"].isin(["denied", "withdrawn"]) & (h["outcome_date"] >= "2009-01-01")]

    summary = {
        "window": f"FY{FY_FROM}-FY{FY_TO}, individual landmark nominations (and amendments) with an HPRB action",
        "heard": outcome_counts(h),
        "documented_pending_raze": outcome_counts(h[h["pending"] == "raze"]),
        "documented_pending_alteration_or_new_construction": outcome_counts(h[h["pending"] == "alteration_or_new"]),
        "no_documented_pending_application": outcome_counts(h[h["pending"] == "none"]),
        "documented_any_share": round(float((h["pending"] != "none").mean()), 3),
        "documented_raze_share": round(float((h["pending"] == "raze").mean()), 3),
        "pending_not_in_nominations": pending.loc[~pending["in_nominations"], ["case_no", "name", "note"]].to_dict("records"),
        "pending_never_heard": pending.loc[pending["outcome"].eq("not_heard"), ["case_no", "name", "application_type", "note"]].to_dict("records"),
        "order_stated": pending.loc[pending["order"].notna(), ["case_no", "name", "order"]].to_dict("records"),
        "raze_after_denial_or_withdrawal": {
            "denied_or_withdrawn_since_2009": int(len(denied_withdrawn_2009)),
            f"with_raze_permit_within_{TIMING_DAYS}_days": int(t["nomination_id"].nunique()),
            "of_which_not_documented_as_pending": sorted(t_only["case_no"].dropna().unique().tolist()),
        },
        "caveats": [
            "Documented counts are lower bounds: HPRB lists a raze application with a nomination only when HPO scheduled it 'if designated'.",
            "The documents show an application pending at the hearing; only two say the raze application came first.",
            "Nominations withdrawn or dropped before a hearing appear only if an agenda or HPO monthly notice listed them (inputs/unheard_nominations.csv); ones withdrawn before being scheduled are invisible.",
            "DOB open data lists issued permits from 2009 only, with no application date; a raze blocked by designation never appears.",
            "Permit-to-nomination links go through address text; 'permit timing' rows were matched by address or lot and are listed for review.",
        ],
    }
    (ANALYSIS / "h2_summary.json").write_text(json.dumps(summary, indent=2, default=str))
