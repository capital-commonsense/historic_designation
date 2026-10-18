"""Validation targets from an exploratory browser pull (2026-10-17).

Exact-count targets apply only to the snapshot taken that day; share targets
apply to every snapshot, so drift in the sources shows up as a failure.
"""

import json

import pandas as pd
import pytest

from historic_preservation.config import ANALYSIS

EXPLORATORY_SNAPSHOT = "2026-10-17"


@pytest.fixture(scope="module")
def summary():
    return json.loads((ANALYSIS / "gis_summary.json").read_text())


@pytest.fixture(scope="module")
def shares():
    return pd.read_csv(ANALYSIS / "designated_shares.csv")


@pytest.fixture(scope="module")
def ward_shares():
    return pd.read_csv(ANALYSIS / "designated_shares_by_ward.csv", dtype={"ward": str})


def share(df, view, metric, zero_tax="included", **where):
    m = (df["view"] == view) & (df["metric"] == metric) & (df["zero_tax"] == zero_tax)
    for k, v in where.items():
        m &= df[k] == v
    (row,) = df[m].to_dict("records")
    return row


@pytest.fixture
def exact_snapshot(summary):
    if summary["snapshot"] != EXPLORATORY_SNAPSHOT:
        pytest.skip("exact counts apply only to the exploratory snapshot")


def test_itspe_record_count(summary, exact_snapshot):
    assert summary["itspe_records"] == 221_667


def test_zoning_lookup_counts(summary, exact_snapshot):
    assert summary["zoning_lookup"]["lots"] == 138_594
    assert summary["zoning_lookup"]["lots_in_district"] == 29_458
    assert summary["zoning_lookup"]["lots_with_landmark"] == 2_695


def test_non_condo_lot_share(shares):
    # Exploratory pull: 21.6% (29,960 of 138,443), +/-0.5 pt.
    assert share(shares, "non_condo", "records")["share"] == pytest.approx(0.216, abs=0.005)


def test_assessed_value_share(shares):
    # Exploratory pull: ~40% ($150B of $380B), +/-2 pt.
    row = share(shares, "all", "assessed_value")
    assert row["total"] == pytest.approx(380e9, rel=0.02)
    assert row["share"] == pytest.approx(0.40, abs=0.02)


def test_land_value_share(shares):
    # Exploratory pull: ~42% ($80B of $190B), +/-2 pt. The exploratory figure reproduces
    # only on strict matches over the full land base. Including square-majority
    # records gives ~49%, mostly federal National Mall parcels (PAR 0316 ...).
    row = share(shares, "strict", "land_value")
    assert row["designated"] == pytest.approx(80e9, rel=0.05)
    all_land = share(shares, "all", "land_value")["total"]
    assert row["designated"] / all_land == pytest.approx(0.42, abs=0.02)


def test_ward_2_lot_share(ward_shares):
    # Exploratory pull: ~77% of Ward 2 lots designated, +/-2 pt.
    assert share(ward_shares, "non_condo", "records", ward="2")["share"] == pytest.approx(0.77, abs=0.02)
