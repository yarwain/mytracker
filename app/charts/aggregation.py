"""Resample time-series metric frames to weekly or monthly averages."""

from typing import Literal

import pandas as pd

Period = Literal["weekly", "monthly"]


def resample_period(df: pd.DataFrame, period: Period) -> pd.DataFrame:
    """Average metric values by week or calendar month."""
    if df.empty:
        return df
    if period == "weekly":
        return aggregate_weekly_average(df)
    return aggregate_monthly_average(df)


def aggregate_weekly_average(df: pd.DataFrame) -> pd.DataFrame:
    """Average values within each Monday-based week, per metric label."""
    frame = df.copy()
    frame["date"] = pd.to_datetime(frame["date"])
    frame["week_start"] = frame["date"] - pd.to_timedelta(frame["date"].dt.dayofweek, unit="D")

    agg: dict[str, tuple[str, str]] = {"value": ("value", "mean"), "unit": ("unit", "first")}
    if "reading_count" in frame.columns:
        agg["reading_count"] = ("reading_count", "sum")
    if "day_count" in frame.columns:
        agg["day_count"] = ("day_count", "sum")

    weekly = (
        frame.groupby(["label", "week_start"], as_index=False)
        .agg(**agg)
        .rename(columns={"week_start": "date"})
        .sort_values(["label", "date"])
    )
    weekly["date"] = weekly["date"].dt.date
    return weekly


def aggregate_monthly_average(df: pd.DataFrame) -> pd.DataFrame:
    """Average values within each calendar month, per metric label."""
    frame = df.copy()
    frame["date"] = pd.to_datetime(frame["date"])
    frame["month_start"] = frame["date"].dt.to_period("M").dt.to_timestamp()

    agg: dict[str, tuple[str, str]] = {"value": ("value", "mean"), "unit": ("unit", "first")}
    if "reading_count" in frame.columns:
        agg["reading_count"] = ("reading_count", "sum")
    if "day_count" in frame.columns:
        agg["day_count"] = ("day_count", "sum")

    monthly = (
        frame.groupby(["label", "month_start"], as_index=False)
        .agg(**agg)
        .rename(columns={"month_start": "date"})
        .sort_values(["label", "date"])
    )
    monthly["date"] = monthly["date"].dt.date
    return monthly


def aggregate_weekly_sum(df: pd.DataFrame) -> pd.DataFrame:
    """Sum values within each Monday-based week, per metric label."""
    frame = df.copy()
    frame["date"] = pd.to_datetime(frame["date"])
    frame["week_start"] = frame["date"] - pd.to_timedelta(frame["date"].dt.dayofweek, unit="D")

    agg: dict[str, tuple[str, str]] = {"value": ("value", "sum"), "unit": ("unit", "first")}
    if "reading_count" in frame.columns:
        agg["reading_count"] = ("reading_count", "sum")
    if "day_count" in frame.columns:
        agg["day_count"] = ("day_count", "sum")

    weekly = (
        frame.groupby(["label", "week_start"], as_index=False)
        .agg(**agg)
        .rename(columns={"week_start": "date"})
        .sort_values(["label", "date"])
    )
    weekly["date"] = weekly["date"].dt.date
    return weekly


def aggregate_monthly_sum(df: pd.DataFrame) -> pd.DataFrame:
    """Sum values within each calendar month, per metric label."""
    frame = df.copy()
    frame["date"] = pd.to_datetime(frame["date"])
    frame["month_start"] = frame["date"].dt.to_period("M").dt.to_timestamp()

    agg: dict[str, tuple[str, str]] = {"value": ("value", "sum"), "unit": ("unit", "first")}
    if "reading_count" in frame.columns:
        agg["reading_count"] = ("reading_count", "sum")
    if "day_count" in frame.columns:
        agg["day_count"] = ("day_count", "sum")

    monthly = (
        frame.groupby(["label", "month_start"], as_index=False)
        .agg(**agg)
        .rename(columns={"month_start": "date"})
        .sort_values(["label", "date"])
    )
    monthly["date"] = monthly["date"].dt.date
    return monthly


def resample_period_sum(df: pd.DataFrame, period: Period) -> pd.DataFrame:
    """Sum metric values by week or calendar month."""
    if df.empty:
        return df
    if period == "weekly":
        return aggregate_weekly_sum(df)
    return aggregate_monthly_sum(df)


MACRO_BREAKDOWN_COLUMNS = (
    "carbohydrates",
    "protein",
    "total_fat",
    "calories",
    "carb_kcal",
    "protein_kcal",
    "fat_kcal",
)


def resample_breakdown(df: pd.DataFrame, period: Period) -> pd.DataFrame:
    """Average daily macro and calorie totals by week or month."""
    if df.empty:
        return df

    frame = df.copy()
    frame["date"] = pd.to_datetime(frame["date"])
    if period == "weekly":
        frame["period_start"] = frame["date"] - pd.to_timedelta(frame["date"].dt.dayofweek, unit="D")
    else:
        frame["period_start"] = frame["date"].dt.to_period("M").dt.to_timestamp()

    aggregated = (
        frame.groupby("period_start", as_index=False)
        .agg({column: "mean" for column in MACRO_BREAKDOWN_COLUMNS})
        .rename(columns={"period_start": "date"})
        .sort_values("date")
    )
    aggregated["date"] = aggregated["date"].dt.date
    return aggregated


def resample_workout_breakdown(df: pd.DataFrame, period: Period) -> pd.DataFrame:
    """Sum workout counts and durations by activity for each period."""
    if df.empty:
        return df

    frame = df.copy()
    frame["date"] = pd.to_datetime(frame["date"])
    if period == "weekly":
        frame["period_start"] = frame["date"] - pd.to_timedelta(frame["date"].dt.dayofweek, unit="D")
    else:
        frame["period_start"] = frame["date"].dt.to_period("M").dt.to_timestamp()

    aggregated = (
        frame.groupby(["period_start", "activity"], as_index=False)
        .agg(
            workout_count=("workout_count", "sum"),
            total_duration=("total_duration", "sum"),
        )
        .rename(columns={"period_start": "date"})
        .sort_values(["date", "activity"])
    )
    aggregated["date"] = aggregated["date"].dt.date
    return aggregated
