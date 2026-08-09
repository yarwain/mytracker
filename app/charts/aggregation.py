"""Resample time-series metric frames to weekly or monthly averages."""

from typing import Literal

import pandas as pd

from app.config import MIN_VALID_LOGGED_DAYS
from app.repositories.energy_balance_repository import energy_balance_diff

Period = Literal["weekly", "monthly"]


def _period_start(frame: pd.DataFrame, period: Period) -> pd.Series:
    if period == "weekly":
        return frame["date"] - pd.to_timedelta(frame["date"].dt.dayofweek, unit="D")
    return frame["date"].dt.to_period("M").dt.to_timestamp()


def valid_logged_days_by_period(daily_df: pd.DataFrame, period: Period) -> pd.Series:
    """Count daily meal-log rows per week or month."""
    if daily_df.empty:
        return pd.Series(dtype="int64")

    frame = daily_df.copy()
    frame["date"] = pd.to_datetime(frame["date"])
    frame["period_start"] = _period_start(frame, period)
    return frame.groupby("period_start")["date"].count()


def mask_low_coverage_periods(
    df: pd.DataFrame,
    valid_day_counts: pd.Series,
    *,
    value_columns: list[str],
    min_valid_days: int = MIN_VALID_LOGGED_DAYS,
) -> pd.DataFrame:
    """Keep period rows but drop values when too few logged days exist."""
    if df.empty:
        return df

    result = df.copy()
    period_keys = pd.to_datetime(result["date"])
    mapped_counts = period_keys.map(valid_day_counts)
    insufficient = mapped_counts.fillna(0) < min_valid_days
    for column in value_columns:
        if column in result.columns:
            result.loc[insufficient, column] = pd.NA
    return result


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
    valid_day_counts = valid_logged_days_by_period(frame, period)
    frame["period_start"] = _period_start(frame, period)

    aggregated = (
        frame.groupby("period_start", as_index=False)
        .agg({column: "mean" for column in MACRO_BREAKDOWN_COLUMNS})
        .rename(columns={"period_start": "date"})
        .sort_values("date")
    )
    aggregated["date"] = aggregated["date"].dt.date
    return mask_low_coverage_periods(
        aggregated,
        valid_day_counts,
        value_columns=list(MACRO_BREAKDOWN_COLUMNS),
    )


ENERGY_BALANCE_COLUMNS = ("spent_kcal", "consumed_kcal", "diff_kcal")


def resample_energy_balance(df: pd.DataFrame, period: Period) -> pd.DataFrame:
    """Sum daily spent and consumed calories by week or month, then compute diff."""
    if df.empty:
        return df

    frame = df.copy()
    frame["date"] = pd.to_datetime(frame["date"])
    consumed_days = frame.loc[
        frame["consumed_kcal"].notna() & (frame["consumed_kcal"] > 0),
        ["date"],
    ]
    valid_day_counts = valid_logged_days_by_period(consumed_days, period)
    frame["period_start"] = _period_start(frame, period)

    aggregated = (
        frame.groupby("period_start", as_index=False)
        .agg(
            spent_kcal=("spent_kcal", "sum"),
            consumed_kcal=("consumed_kcal", "sum"),
        )
        .rename(columns={"period_start": "date"})
        .sort_values("date")
    )
    aggregated["date"] = aggregated["date"].dt.date
    aggregated = mask_low_coverage_periods(
        aggregated,
        valid_day_counts,
        value_columns=["consumed_kcal"],
    )
    aggregated["diff_kcal"] = energy_balance_diff(
        aggregated["consumed_kcal"],
        aggregated["spent_kcal"],
    )
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
