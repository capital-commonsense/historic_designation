"""inputs/chart_titles.json: one entry per chart, each null (computed headline) or text."""

import json

from historic_preservation.charts import TITLES
from historic_preservation.config import CHARTS_OUT


def test_every_chart_has_an_entry_and_no_strays():
    charts = {p.name.removesuffix(".data.csv") for p in CHARTS_OUT.glob("*.data.csv")} | {"comps_designated_land_video"}
    assert set(json.loads(TITLES.read_text())) == charts


def test_overrides_are_null_or_text():
    assert all(v is None or (isinstance(v, str) and v.strip()) for v in json.loads(TITLES.read_text()).values())
