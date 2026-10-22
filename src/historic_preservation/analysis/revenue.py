"""Property tax billed on historic and other property, TY2018 onward, and a growth-gap scenario.

Tax is what the roll records as levied on each record for each tax year (itspe_tax_history:
nine prior years plus the current year's two halves), so it reflects rates, the homestead
deduction, the assessment cap and relief as billed. Records retired since TY2018 (subdivided,
consolidated, converted to condominiums) are not on today's roll, so early years run a little low.
A record counts as historic in a year once its district or landmark had been designated
(undated designations count from the start).

The scenario is the DC Policy Center's (April 2022): from 2006 to 2021, the residential
buildings in districts designated before 2006 grew 4.9% a year in total assessed value, the
rest of the city's 6.2% (inputs/dcpc_growth_2006_2021.csv). Compounding that gap from 2006 onto
the tax billed on those buildings gives what they would have paid had they kept pace. It is
not a measured loss: DCPC's gap includes new construction outside the districts and differences
in where neighborhoods started in 2006, and DCPC does not attribute it to designation. A second
line uses DCPC's existing-stock figures (buildings standing in 2006) only.

The roll's own years test how much of the gap is geography: on residential records billed every
year since TY2018, the tax on homes in pre-2006 districts is grown at the rate of never-designated
homes citywide, and again ward by ward (summed). The two answers bracket how much of the gap is
about where in the city growth happened rather than inside or outside a district.
"""

import json

import pandas as pd

from historic_preservation.analysis import eras
from historic_preservation.config import ANALYSIS, INPUTS, JOINED, NORMALIZED

FIRST_YEAR, DCPC_BASE = 2018, 2006


def dcpc() -> dict:
    d = pd.read_csv(INPUTS / "dcpc_growth_2006_2021.csv").set_index("measure")
    total = d.loc["total_value_growth_annual"]
    stock = d.loc["existing_stock_growth_2006_2021"]
    return {"total": (1 + total["other"]) / (1 + total["historic"]),
            "existing_stock": ((1 + stock["other"]) / (1 + stock["historic"])) ** (1 / 15)}


def records() -> pd.DataFrame:
    j = pd.read_parquet(JOINED / "itspe_status.parquet")
    j["ward"] = j["ward"].fillna(j["zl_ward"])
    j["residential"] = eras.property_class(j["proptype"]) == "residential"
    j["first_date"] = eras.record_first_dates(j)["first_date"].reindex(j.index)
    j["district_first"] = eras.lot_first_dates(j, eras.district_first_dates())["first_date"].reindex(j.index)
    h = pd.read_parquet(NORMALIZED / "itspe_tax_history.parquet")
    m = h[h["tax_year"] >= FIRST_YEAR].merge(
        j[["ssl", "ward", "designated", "residential", "first_date", "district_first"]], on="ssl", how="left")
    year = m["tax_year"].astype(int)
    m["historic"] = m["designated"].fillna(False) & (m["first_date"].isna() | (m["first_date"].dt.year <= year))
    m["pre2006_district_home"] = m["residential"].fillna(False) & (m["district_first"].dt.year < DCPC_BASE)
    return m


def cagr(p: pd.DataFrame, first: int, last: int) -> dict:
    return {str(k): round(float((p.loc[last, k] / p.loc[first, k]) ** (1 / (last - first)) - 1), 4) for k in p.columns}


def gap_at_other_rate(panel: pd.DataFrame, first: int, last: int) -> float:
    """Tax the pre-2006 district homes would pay in `last` had they grown from `first` at the
    never-designated homes' rate, minus what they pay."""
    p = panel.pivot_table(index="tax_year", columns="pre2006_district_home", values="tax", aggfunc="sum")
    if True not in p or p[True].isna().any():
        return 0.0
    return float(p.loc[first, True] * p.loc[last, False] / p.loc[first, False] - p.loc[last, True])


def run() -> None:
    path = NORMALIZED / "itspe_tax_history.parquet"
    if not path.exists():
        return
    m = records()
    gap = dcpc()
    last = int(m["tax_year"].max())
    t = pd.DataFrame({
        "other": m[~m["historic"]].groupby("tax_year")["tax"].sum(),
        "historic": m[m["historic"]].groupby("tax_year")["tax"].sum(),
        "historic_residential": m[m["historic"] & m["residential"].fillna(False)].groupby("tax_year")["tax"].sum(),
        "pre2006_district_homes": m[m["pre2006_district_home"]].groupby("tax_year")["tax"].sum(),
    })
    t.index = t.index.astype(int)
    for name, rate in gap.items():
        t[f"scenario_gap_{name}"] = t["pre2006_district_homes"] * (rate ** (t.index - DCPC_BASE) - 1)
    t.to_csv(ANALYSIS / "property_tax_by_year.csv")

    # The same comparison in the tax roll's own years: residential records billed in every year,
    # in pre-2006 districts against records never designated.
    years = m.groupby("ssl")["tax_year"].nunique()
    panel = m[m["ssl"].isin(years[years == last - FIRST_YEAR + 1].index) & m["residential"].fillna(False)]
    panel = panel[panel["pre2006_district_home"] | ~panel["designated"].fillna(False)]
    by = panel.pivot_table(index="tax_year", columns="pre2006_district_home", values="tax", aggfunc="sum")
    by = by.rename(columns={True: "pre2006_district_homes", False: "never_designated_homes"})
    all_res = m[m["residential"].fillna(False) & (m["pre2006_district_home"] | ~m["designated"].fillna(False))]
    by_all = all_res.pivot_table(index="tax_year", columns="pre2006_district_home", values="tax", aggfunc="sum")
    by_all = by_all.rename(columns={True: "pre2006_district_homes", False: "never_designated_homes"})
    by_ward = {str(w): round(gap_at_other_rate(g, FIRST_YEAR, last)) for w, g in panel.groupby("ward")}
    summary = {
        "years": [FIRST_YEAR, last],
        "tax_last_year": {k: round(float(t.loc[last, k])) for k in t.columns},
        "historic_share": {str(y): round(float(r["historic"] / (r["historic"] + r["other"])), 3) for y, r in t.iterrows()},
        "scenario_gap_cumulative": {k: round(float(t[f"scenario_gap_{k}"].sum())) for k in gap},
        "dcpc_annual_ratio": {k: round(float(v), 4) for k, v in gap.items()},
        "residential_tax_cagr_same_records": cagr(by, FIRST_YEAR, last),
        "residential_tax_cagr_same_records_n": {"pre2006_district_homes": int(panel.loc[panel["pre2006_district_home"], "ssl"].nunique()),
                                                "never_designated_homes": int(panel.loc[~panel["pre2006_district_home"], "ssl"].nunique())},
        "residential_tax_cagr_all_records": cagr(by_all, FIRST_YEAR, last),
        "same_records_gap_last_year": {"citywide_rate": round(gap_at_other_rate(panel, FIRST_YEAR, last)),
                                       "within_ward_rates": sum(by_ward.values()), "by_ward": by_ward},
        "caveats": [
            "Tax is as levied on today's roll records for each tax year; records retired since TY2018 are missing, so early years run low.",
            "Historic in a year: designated by that year (district or landmark; undated designations count throughout).",
            "Scenario: DC Policy Center (2022) total-value growth gap for residential buildings in pre-2006 districts, 2006-21 "
            "(6.2% vs 4.9% a year), compounded from 2006 onto those buildings' tax; carried past 2021 at the same rate. "
            "Includes new construction outside the districts; DCPC does not attribute the gap to designation.",
            "Existing-stock line: DCPC's appreciation of buildings standing in 2006 (94% vs 85%, 2006-21).",
            "Scaling tax by value ignores the homestead deduction and assessment cap, which do not scale.",
            "Commercial, landmark-only and post-2006 district property gets no scenario: DCPC measured residential districts designated before 2006.",
        ],
    }
    (ANALYSIS / "property_tax_summary.json").write_text(json.dumps(summary, indent=1))
