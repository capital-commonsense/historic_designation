"""Value under district protection by era of first DC designation (H9).

A district's first date is its earliest event that put it on a DC list:
the 1950 Old Georgetown Act, a DC listing, or a designation. A 1964
"preliminary identification" does not count (inputs/district_dates.csv
records it as preliminary_listing). A lot inside overlapping districts
takes the earliest first date among them.

Limitation: only current boundaries are published, so lots added by a later
expansion are attributed to the district's original designation year.
Districts with recorded expansions are listed in district_first_dates.csv
(has_expansion) so findings can say so.
"""

import pandas as pd

from historic_preservation.config import INPUTS

FIRST_EVENTS = ("established_by_act", "dc_listing", "designated")
ERA_ORDER = ["1950", "1964 list", "1960s other", "1970s", "1980s", "1990s", "2000s", "2010s", "2020s", "undated"]


def district_first_dates() -> pd.DataFrame:
    ev = pd.read_csv(INPUTS / "district_dates.csv", parse_dates=["date"])
    first = (
        ev[ev["event"].isin(FIRST_EVENTS)]
        .sort_values("date")
        .groupby("district")
        .first()[["event", "date", "source_doc", "source_page", "confidence"]]
        .rename(columns={"event": "first_event", "date": "first_date"})
    )
    expansions = ev[ev["event"].isin(["expanded", "boundary_change"])].groupby("district")["date"].agg(
        lambda s: "; ".join(d.date().isoformat() for d in s.dropna())
    )
    first["expansions"] = expansions.reindex(first.index).fillna("")
    first["has_expansion"] = first["expansions"] != ""
    first["era"] = first["first_date"].map(era)
    return first.reset_index()


def era(d) -> str:
    if pd.isna(d):
        return "undated"
    if d.year == 1950:
        return "1950"
    if d == pd.Timestamp("1964-11-08"):
        return "1964 list"
    if d.year < 1970:
        return "1960s other"
    return f"{d.year // 10 * 10}s"


def lot_first_dates(joined: pd.DataFrame, firsts: pd.DataFrame) -> pd.DataFrame:
    """Per ITSPE record in a district: earliest first date among its districts."""
    dates = firsts.set_index("district")["first_date"]
    names = joined.loc[joined["in_district"], "historic_districts"].str.split(";").explode()
    d = names.map(dates)
    unknown = sorted(set(names[d.isna()]))
    if unknown:
        raise ValueError(f"districts missing from inputs/district_dates.csv: {unknown}")
    earliest = d.groupby(level=0).min()
    out = joined.loc[earliest.index].copy()
    out["first_date"] = earliest
    out["era"] = out["first_date"].map(era)
    out["district_count"] = names.groupby(level=0).size()
    return out


def value_by_era(lots: pd.DataFrame) -> pd.DataFrame:
    g = lots.groupby("era").agg(
        records=("ssl", "size"),
        assessed_value=("assessment", "sum"),
        land_value=("newland", "sum"),
        assessed_value_taxable=("assessment", lambda s: s[~lots.loc[s.index, "zero_tax"]].sum()),
    )
    return g.reindex([e for e in ERA_ORDER if e in g.index]).reset_index()
