"""Analysis stage: designated shares of lots and value (H8) from the joined tax roll.

Every share is reported under three record views and with and
without zero-tax property:
  all       every ITSPE record, condo units included via the join fallbacks
  non_condo ITSPE records whose PROPTYPE is not a condominium type (inferred)
  strict    records matched to a lot exactly (SSL, PRESSL or CONDORELATE)
"""

import json

import pandas as pd

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
    print("analysis: wrote designated_shares.csv, designated_shares_by_ward.csv, gis_summary.json")
