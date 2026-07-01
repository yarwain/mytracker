"""Tests for chart scale helpers."""

import pandas as pd

from app.charts.scales import tight_y_domain


def test_tight_y_domain_adds_padding() -> None:
    low, high = tight_y_domain(pd.Series([10.0, 12.0, 11.0]), padding_ratio=0.1)
    assert low < 10.0
    assert high > 12.0
    assert high - low < 3.0


def test_tight_y_domain_handles_flat_series() -> None:
    low, high = tight_y_domain(pd.Series([58.0, 58.0]))
    assert low < 58.0
    assert high > 58.0
