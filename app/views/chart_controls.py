"""Shared Streamlit controls for metric trend charts."""

import pandas as pd
import streamlit as st

from app.charts.aggregation import Period, resample_period, resample_period_sum


def render_period_filter(*, key: str, label: str = "Period") -> Period:
    """Render a compact weekly vs monthly selector."""
    selected = st.segmented_control(
        label,
        options=["Weekly", "Monthly"],
        default=st.session_state.get(key, "Weekly"),
        key=key,
    )
    return "weekly" if selected == "Weekly" else "monthly"


def available_years(df: pd.DataFrame) -> list[int]:
    """Return sorted years present in the dataset."""
    dates = pd.to_datetime(df["date"])
    return sorted(dates.dt.year.unique().tolist())


def render_year_filter(available: list[int], *, key: str, label: str = "Years") -> list[int]:
    """Render a compact multiselect for choosing which years to display."""
    selected = st.multiselect(
        label,
        options=available,
        default=available,
        placeholder="Choose years",
        key=key,
    )
    return selected or available


def render_year_period_row(
    year_options: list[int],
    *,
    year_key: str,
    period_key: str,
    year_width: int = 2,
    period_width: int = 1,
) -> tuple[list[int], Period]:
    """Render year and period selectors on one row."""
    year_col, period_col = st.columns([year_width, period_width])
    with year_col:
        years = render_year_filter(year_options, key=year_key)
    with period_col:
        period = render_period_filter(key=period_key)
    return years, period


def filter_by_years(df: pd.DataFrame, years: list[int]) -> pd.DataFrame:
    """Return rows whose date falls within the selected years."""
    dates = pd.to_datetime(df["date"])
    mask = dates.dt.year.isin(years)
    return df.loc[mask].copy()


def apply_period(df: pd.DataFrame, period: Period) -> pd.DataFrame:
    """Resample chart data to the selected period."""
    return resample_period(df, period)


def apply_period_sum(df: pd.DataFrame, period: Period) -> pd.DataFrame:
    """Resample chart data to the selected period using sums."""
    return resample_period_sum(df, period)
