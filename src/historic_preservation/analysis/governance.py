"""DCPL governance from its 990s and board page: aggregates only, no individuals.

Rosters (inputs/dcpl_board.csv) give names and credentials as listed; employers
are known only for the current board page, so composition over time is limited
to listed credentials (AIA/FAIA marks an architect). Part VI answers come from
inputs/dcpl_990_lines.csv.
"""

import json

import pandas as pd

from historic_preservation.config import ANALYSIS, INPUTS

ARCHITECT = r"\b(?:F?AIA|AJA)\b"  # "AJA" is the 2013 roster's OCR of "AIA"


def run() -> None:
    board = pd.read_csv(INPUTS / "dcpl_board.csv", dtype=str).fillna("")
    # Per person, not per roster: some rosters (FY2012, FY2014-15) print no credentials at all.
    credentialed = set(board.loc[board["credentials_listed"].str.contains(ARCHITECT), "person_key"])
    board["architect_credential"] = board["person_key"].isin(credentialed)
    periods = sorted(board["period"].unique())
    by_period = board.groupby("period").agg(
        trustees=("person_key", "nunique"),
        architect_credential=("architect_credential", "sum"),
    )
    by_period["architect_share"] = (by_period["architect_credential"] / by_period["trustees"]).round(3)
    seen = board.groupby("person_key")["period"].nunique()
    turnover = {}
    for prev, cur in zip(periods, periods[1:]):
        a = set(board.loc[board["period"] == prev, "person_key"])
        b = set(board.loc[board["period"] == cur, "person_key"])
        turnover[f"{prev}->{cur}"] = {"stayed": len(a & b), "left": len(a - b), "joined": len(b - a)}
    current = board[board["period"] == periods[-1]]

    lines = pd.read_csv(INPUTS / "dcpl_990_lines.csv", dtype=str)
    vi = lines[lines["form_line"].str.match(r"Part VI line ")]
    policies = vi.pivot(index="description_as_filed", columns="tax_period", values="value")

    summary = {
        "rosters": by_period.reset_index().to_dict("records"),
        "people": int(seen.size),
        "people_on_4_or_more_rosters": int((seen >= 4).sum()),
        "turnover": turnover,
        "current_affiliation_categories": current["affiliation_category"].value_counts().to_dict(),
        "current_source": current["source_doc"].iloc[0],
        "part_vi": policies.to_dict(),
        "caveats": [
            "Employers are listed only on the current board page; earlier rosters give names and credentials.",
            "A trustee counts as architect-credentialed if any roster prints AIA/FAIA for them; one without a printed credential may still be an architect.",
            "One 2011 roster name ('John D. Ferrari') is read as the trustee listed as John DeFerrari in later years (inferred from spelling).",
        ],
    }
    (ANALYSIS / "dcpl_governance.json").write_text(json.dumps(summary, indent=1, default=str))
