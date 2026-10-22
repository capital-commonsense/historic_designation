import pandas as pd
import pytest

from historic_preservation.analysis.comps import dc_designated_share_trend
from historic_preservation.config import ANALYSIS


def test_dc_designated_share_trend_reproduces_post_values():
    trend = dc_designated_share_trend(pd.read_csv(ANALYSIS / "comps_by_year.csv"))

    assert trend["start_year"] == 1964
    assert trend["slope_percentage_points_per_year"] == pytest.approx(0.2212, abs=0.0001)
    assert trend["r_squared"] == pytest.approx(0.9621, abs=0.0001)
    assert trend["linear_extrapolation_year_at_100_percent"] == pytest.approx(2399, abs=1)
    assert trend["extrapolation_is_forecast"] is False
