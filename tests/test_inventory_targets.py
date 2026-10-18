"""Validation targets that depend on the DC Inventory and inputs/district_dates.csv.

Era values from the exploratory pull are compared only where the era
definitions match. Known differences (documented in data/README.md):
  - the exploratory pull left five districts undated ($1.9B); all are dated now
  - 1968 DC listings (Federal Triangle etc.) are their own "1960s other" bucket
"""

import json

import pandas as pd
import pytest

from historic_preservation.config import ANALYSIS, INPUTS, NORMALIZED


@pytest.fixture(scope="module")
def eras():
    return pd.read_csv(ANALYSIS / "value_by_designation_era.csv").set_index("era")


def test_inventory_1964_listings():
    # Exploratory pull: 287 entries dated 1964 (+/-3); the Inventory itself says 289.
    n = json.loads((ANALYSIS / "inventory_summary.json").read_text())["entries_dc_listed_1964_11_08"]
    assert n == pytest.approx(287, abs=3)


@pytest.mark.parametrize("era, billions", [("1950", 12.8), ("1980s", 17.2), ("1990s", 12.9), ("2000s", 3.7)])
def test_district_value_by_era(eras, era, billions):
    assert eras.loc[era, "assessed_value"] / 1e9 == pytest.approx(billions, rel=0.05)


def test_every_gis_district_has_a_first_date():
    firsts = pd.read_csv(ANALYSIS / "district_first_dates.csv")
    gis = pd.read_csv(NORMALIZED / "historic_districts.csv")
    assert set(gis["name"]) <= set(firsts["district"])
    assert firsts["first_date"].notna().all()


def test_district_dates_have_sources():
    ev = pd.read_csv(INPUTS / "district_dates.csv")
    assert ev["source_doc"].notna().all()
    assert ev["confidence"].isin(["high", "medium", "low"]).all()
