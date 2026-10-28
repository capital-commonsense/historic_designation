"""Parsing HPO's case log (normalize/case_log.py): the layouts that need special handling, and the
release's totals as counted from the document (2026-10-27 release)."""

import pandas as pd
import pytest

from historic_preservation.config import NORMALIZED
from historic_preservation.normalize.case_log import parse

SAMPLE = "\n".join([
    "RECORD OF HPRB ACTIONS ON DESIGNATION APPLICATIONS",
    "Property\tCase Number\tAction Date",
    "Barney Circle Historic District\t08-01\tWithdrawn March 14, 2025",
    "National Association for the Relief of Destitute",
    "Colored Women and Children\t\t\t22-09\t\tDesignated July 28, 2022",
    "Folger Shakespeare Library amendment\t2\t22-16",
    "Bullfinch Gatehouses and Gateposts amendment 21-16\t       Forwarded to National Register",
    "Scottish Rite Temple amendment\t19-06                 Denied May 23, 2019 and February 23, 2023",
    "Telephone multiple-property\t\tAdopted April 27, 2006",
    "Carl C. Mueller House\t04-04\tWithdrawn May 2004",
    "Central Public Library amendment\t20-04\tForwarded FY2020",
    "Lunch Room and Oyster Shucking Shed\t12-03\tSuperseded by 15-20",
    " PAGE 8",
])


@pytest.fixture(scope="module")
def sample():
    return parse(SAMPLE).set_index("name")


def test_wrapped_name_joins_the_next_line(sample):
    row = sample.loc["National Association for the Relief of Destitute Colored Women and Children"]
    assert (row["case_no"], row["action"]) == ("22-09", "designated")


def test_stray_column_stays_in_the_name(sample):
    row = sample.loc["Folger Shakespeare Library amendment 2"]
    assert (row["case_no"], row["action"]) == ("22-16", "none")


def test_case_number_without_a_tab(sample):
    assert sample.loc["Bullfinch Gatehouses and Gateposts amendment", "case_no"] == "21-16"


def test_last_of_two_dates_is_the_action_date(sample):
    assert sample.loc["Scottish Rite Temple amendment", "action_date"] == pd.Timestamp("2023-02-23")


def test_framework_document_without_a_case_number(sample):
    row = sample.loc["Telephone multiple-property"]
    assert (row["case_no"], row["action"]) == ("", "adopted")


@pytest.mark.parametrize("name, precision", [
    ("Carl C. Mueller House", "month"), ("Central Public Library amendment", "fy"),
    ("Barney Circle Historic District", "day"),
])
def test_date_precision(sample, name, precision):
    assert sample.loc[name, "date_precision"] == precision


def test_superseded_by(sample):
    assert sample.loc["Lunch Room and Oyster Shucking Shed", "superseded_by"] == "15-20"


def test_case_fy_from_the_case_number(sample):
    assert sample.loc["Barney Circle Historic District", "case_fy"] == 2008


def test_release_totals():
    path = NORMALIZED / "hpo_case_log.csv"
    if not path.exists():
        pytest.skip("no case log release in data/raw/manual/records_request/")
    log = pd.read_csv(path, dtype={"case_no": str})
    if set(log["release"]) != {"2026-10-27"}:
        pytest.skip("totals are for the 2026-10-27 release")
    assert len(log) == 452
    assert log["action"].value_counts().to_dict() == {
        "designated": 317, "withdrawn": 43, "denied": 29, "none": 26, "adopted": 13, "amended": 11,
        "forwarded": 5, "superseded": 4, "continued": 1, "revoked": 1, "updated": 1, "listed": 1}


def test_every_log_case_is_matched_or_explained():
    """join/case_log.py's comparison after the log is merged into nominations.csv: anything other than
    agreement has a recorded reason."""
    from historic_preservation.config import INPUTS, JOINED
    path = JOINED / "case_log_comparison.csv"
    if not path.exists():
        pytest.skip("no case log comparison")
    c = pd.read_csv(path, dtype=str)
    # Superseded cases continue under another number; they are not nominations of their own.
    lost = c[(c["status"] == "log_only") & ~c["action"].eq("superseded")]
    assert lost.empty, lost[["case_no", "name_log"]].to_string()
    # Unresolved outcome conflicts stop the build (inputs/case_log_review.csv); none should reach here.
    assert not (c["status"] == "outcome_differs").any()
    # Cases opened after the log was compiled: the log's newest case is 26-06.
    newer = c.loc[c["status"] == "scrape_only", "case_no"]
    assert (newer > "26-06").all(), sorted(newer)
    # Date disagreements carry a note in reconciliation_notes.csv.
    notes = set(pd.read_csv(INPUTS / "reconciliation_notes.csv")["name"])
    undated = c[(c["status"] == "date_differs") & ~c["name_scrape"].isin(notes)]
    assert undated.empty, undated[["case_no", "name_scrape"]].to_string()
