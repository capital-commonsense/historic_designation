"""Checks for the H2 permit work: address keys, outcome negations, the review file's links."""

import pandas as pd
import pytest

from historic_preservation.addresses import keys
from historic_preservation.config import JOINED


@pytest.mark.parametrize("text, expected", [
    ("1132, 1140, and 1146 3rd Street, SE", ["1132 3 ST SE", "1140 3 ST SE", "1146 3 ST SE"]),
    ("104-108 Rhode Island Avenue NE", ["104 RHODE ISLAND AVE NE", "106 RHODE ISLAND AVE NE", "108 RHODE ISLAND AVE NE"]),
    ("1500 Massachusetts Avenue, N.W.", ["1500 MASSACHUSETTS AVE NW"]),
    ("4615 14^(th) Street, NW", ["4615 14 ST NW"]),
    ("5609 1ST ST NE WASHINGTON DC 20011-2415", ["5609 1 ST NE"]),
])
def test_address_keys(text, expected):
    assert keys(text) == expected


def test_range_keeps_one_side_of_street():
    # 1313-1333 H Street NE: odd numbers only; the evens are across the street.
    assert all(int(k.split()[0]) % 2 for k in keys("1313-1333 H Street, NE"))


@pytest.fixture(scope="module")
def noms():
    return pd.read_csv(JOINED / "nominations.csv", dtype={"case_no": str}).set_index("case_no", drop=False)


def test_negated_designation_is_denial(noms):
    # 2009-5_HPRB_Actions.pdf: "The Board voted to not designate the properties".
    assert noms.loc["09-05", "outcome"] == "denied"


def test_house_number_list_is_not_a_name(noms):
    # "917, 919 and 921 6th Street NW, Case 20-12" was named "917".
    assert noms.loc["20-12", "address"].startswith("917, 919")


def test_pending_applications_link_to_nominations():
    p = pd.read_csv(JOINED / "h2_pending_applications.csv", dtype={"case_no": str})
    assert p["in_nominations"].all()


def test_unheard_nominations_are_in_table(noms):
    # HPO notices: noticed for a hearing, never acted on (inputs/unheard_nominations.csv).
    assert noms.loc["18-05", "outcome"] == "not_heard"  # Clapper House, razed 2018
    assert noms.loc["17-11", "outcome"] == "withdrawn"  # Square 653 Rowhouses
    assert noms.loc["07-36", "outcome"] == "denied"  # "recommending the Board not designate"
