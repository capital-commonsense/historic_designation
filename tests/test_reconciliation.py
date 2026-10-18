"""Regression checks for the nomination reconciliation (join/nominations.py).

Each case below was a real mis-merge or mis-parse found while reviewing
reconciliation.csv; the source line that settles it is noted.
"""

import re

import pandas as pd
import pytest

from historic_preservation.config import JOINED, NORMALIZED
from historic_preservation.normalize.hprb import CASE, case_no


@pytest.fixture(scope="module")
def noms():
    return pd.read_csv(JOINED / "nominations.csv", dtype={"case_no": str})


@pytest.fixture(scope="module")
def updates():
    return pd.read_csv(NORMALIZED / "inventory_update_items.csv")


@pytest.mark.parametrize("text, expected", [
    ("Peyser Building, 1518 K Street, NW, Case #11-07.", "11-07"),
    ("Immaculata Seminary, 4340 Nebraska Avenue, NW, #11-08.", "11-08"),  # bare '#' (2011 lists)
    ("2829 16th Street, NW, Case\n#13-013.", "13-13"),  # zero-padded (late 2012)
])
def test_case_number_forms(text, expected):
    assert case_no(CASE.search(text)) == expected


@pytest.mark.parametrize("text", ["Raze #07-58 and #07-59", "311 9th Street, NE #06-077", "1445 Swann Street, NW, #08-001"])
def test_permit_numbers_are_not_cases(text):
    m = CASE.search(text)
    assert m is None or re.match(r"\s*HPA", m.group(0))


def test_two_column_attributions(updates):
    # FY2012 update: Peyser's attribution reads June 28, 2012 (it was once given Dorsch's Nov 17, 2011).
    peyser = updates[updates["name"].str.startswith("Peyser Building", na=False)].iloc[0]
    assert peyser["designated"] == "June 28, 2012"
    # FY2022 report p9 (a two-page spread): National Geographic Society was missed entirely.
    assert (updates["name"] == "National Geographic Society").any()


def test_shared_case_number_does_not_merge(noms):
    # HPRB actions Jan 2010 print "Case #10-04" for both The Flagler and Milton Hall.
    rows = noms[noms["name"].isin(["The Flagler", "Milton Hall"])]
    assert rows["nomination_id"].nunique() == 2


def test_numbered_names_do_not_merge(noms):
    engines = noms[noms["name"].str.contains(r"Engine Company (?:No\. )?2[267]\b", na=False, regex=True)]
    assert engines["nomination_id"].nunique() >= 3


def test_date_conflicts_are_flagged(noms):
    flagged = set(noms.loc[noms["date_conflict"].notna(), "case_no"])
    assert {"11-16", "13-19"} <= flagged
