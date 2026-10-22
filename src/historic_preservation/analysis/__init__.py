"""Analysis stage: designated shares of lots and value (H8) from the joined tax roll.

Every share is reported under three record views and with and
without zero-tax property:
  all       every ITSPE record, condo units included via the join fallbacks
  non_condo ITSPE records whose PROPTYPE is not a condominium type (inferred)
  strict    records matched to a lot exactly (SSL, PRESSL or CONDORELATE)
"""

import json

import pandas as pd

from historic_preservation.analysis import courts, coverage, eras, governance, grants, comps, mayors_agent, permits, revenue, review_types, staff
from historic_preservation.config import ANALYSIS, JOINED, NORMALIZED
from historic_preservation.join import STRICT_METHODS

METRICS = {"records": None, "assessed_value": "assessment", "land_value": "newland"}


def views(j: pd.DataFrame) -> dict[str, pd.Series]:
    return {
        "all": pd.Series(True, index=j.index),
        "non_condo": ~j["is_condo"],
        "strict": j["match_method"].isin(STRICT_METHODS),
    }


def shares(j: pd.DataFrame, by: str | None = None) -> pd.DataFrame:
    """Tidy table: view x exempt-handling x metric (x group) -> designated, total, share."""
    rows = []
    for view, vmask in views(j).items():
        for exempt, emask in (("included", True), ("excluded", ~j["zero_tax"])):
            sub = j[vmask & emask]
            groups = sub.groupby(by) if by else [(None, sub)]
            for key, g in groups:
                for metric, col in METRICS.items():
                    w = pd.Series(1.0, index=g.index) if col is None else g[col].fillna(0)
                    total, designated = w.sum(), w[g["designated"]].sum()
                    row = {"view": view, "zero_tax": exempt, "metric": metric}
                    if by:
                        row[by] = key
                    rows.append(row | {
                        "designated": designated,
                        "total": total,
                        "share": designated / total if total else float("nan"),
                    })
    return pd.DataFrame(rows)


def zoning_lookup_counts(zl: pd.DataFrame) -> dict:
    return {
        "lots": len(zl),
        "lots_in_district": int(zl["in_district"].sum()),
        "lots_with_landmark": int(zl["is_landmark"].sum()),
        "lots_designated": int(zl["designated"].sum()),
    }


def run() -> None:
    ANALYSIS.mkdir(parents=True, exist_ok=True)
    j = pd.read_parquet(JOINED / "itspe_status.parquet")
    zl = pd.read_parquet(NORMALIZED / "zoning_lookup.parquet")
    snapshot = json.loads((NORMALIZED / "SNAPSHOT.json").read_text())["snapshot"]

    shares(j).to_csv(ANALYSIS / "designated_shares.csv", index=False)
    shares(j[j["ward"].notna()], by="ward").to_csv(ANALYSIS / "designated_shares_by_ward.csv", index=False)
    summary = {
        "snapshot": snapshot,
        "itspe_records": len(j),
        "itspe_extract_date_max": str(j["extractdat"].max()),
        "itspe_extract_date_mode": str(j["extractdat"].mode().iloc[0]),
        "match_methods": j["match_method"].value_counts().to_dict(),
        "zoning_lookup": zoning_lookup_counts(zl),
    }
    (ANALYSIS / "gis_summary.json").write_text(json.dumps(summary, indent=2))

    firsts = eras.district_first_dates()
    firsts.to_csv(ANALYSIS / "district_first_dates.csv", index=False)
    lots = eras.lot_first_dates(j, firsts)
    eras.value_by_era(lots).to_csv(ANALYSIS / "value_by_designation_era.csv", index=False)
    eras.value_by_era(lots[~lots["status_inferred"]]).to_csv(
        ANALYSIS / "value_by_designation_era_strict.csv", index=False
    )

    inv = pd.read_csv(NORMALIZED / "inventory_2009_entries.csv")
    inventory = {
        "entries": len(inv),
        "entries_dc_listed_1964_11_08": int(inv["dc_listing"].fillna("").str.contains("November 8, 1964").sum()),
    }
    (ANALYSIS / "inventory_summary.json").write_text(json.dumps(inventory, indent=2))
    coverage.run()
    courts.run()
    governance.run()
    mayors_agent.run()
    permits.run()
    staff.run()
    comps.run()
    revenue.run()
    grants.run()
    review_types.run()
    print("analysis: wrote designated shares, district eras, inventory summary, coverage, court appeals, DCPL governance, Mayor's Agent, H2 permits")
