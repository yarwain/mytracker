from datetime import date

import pandas as pd

from app.charts.aggregation import resample_energy_balance
from app.charts.energy_balance_chart import EnergyBalanceChart


def test_resample_energy_balance_sums_daily_totals() -> None:
    frame = pd.DataFrame(
        {
            "date": [
                date(2025, 1, 6),
                date(2025, 1, 7),
                date(2025, 1, 8),
                date(2025, 1, 9),
                date(2025, 1, 13),
            ],
            "spent_kcal": [500.0, 600.0, 550.0, 650.0, 700.0],
            "consumed_kcal": [1800.0, 1700.0, 1650.0, 1750.0, 1600.0],
        }
    )

    weekly = resample_energy_balance(frame, "weekly")
    assert len(weekly) == 2
    first_week = weekly.iloc[0]
    second_week = weekly.iloc[1]
    assert first_week["spent_kcal"] == 2300.0
    assert first_week["consumed_kcal"] == 6900.0
    assert first_week["diff_kcal"] == 4600.0
    assert second_week["spent_kcal"] == 700.0
    assert pd.isna(second_week["consumed_kcal"])
    assert pd.isna(second_week["diff_kcal"])


def test_resample_energy_balance_skips_diff_without_consumed() -> None:
    frame = pd.DataFrame(
        {
            "date": [date(2025, 1, 6), date(2025, 1, 7)],
            "spent_kcal": [500.0, 600.0],
            "consumed_kcal": [pd.NA, pd.NA],
        }
    )

    weekly = resample_energy_balance(frame, "weekly")
    assert len(weekly) == 1
    assert weekly.iloc[0]["spent_kcal"] == 1100.0
    assert pd.isna(weekly.iloc[0]["consumed_kcal"])
    assert pd.isna(weekly.iloc[0]["diff_kcal"])


def test_resample_energy_balance_masks_consumed_with_few_logged_days() -> None:
    frame = pd.DataFrame(
        {
            "date": [date(2025, 1, 6), date(2025, 1, 7), date(2025, 1, 8), date(2025, 1, 9)],
            "spent_kcal": [500.0, 600.0, 700.0, 800.0],
            "consumed_kcal": [1800.0, 1700.0, 1600.0, pd.NA],
        }
    )

    weekly = resample_energy_balance(frame, "weekly")
    assert len(weekly) == 1
    assert weekly.iloc[0]["spent_kcal"] == 2600.0
    assert pd.isna(weekly.iloc[0]["consumed_kcal"])
    assert pd.isna(weekly.iloc[0]["diff_kcal"])


def test_resample_energy_balance_masks_consumed_with_few_logged_days_monthly() -> None:
    frame = pd.DataFrame(
        {
            "date": [
                date(2025, 1, 6),
                date(2025, 1, 7),
                date(2025, 1, 8),
                date(2025, 1, 9),
                date(2025, 2, 3),
                date(2025, 2, 4),
                date(2025, 2, 5),
                date(2025, 2, 6),
                date(2025, 2, 7),
            ],
            "spent_kcal": [500.0, 600.0, 700.0, 800.0, 400.0, 450.0, 500.0, 550.0, 600.0],
            "consumed_kcal": [1800.0, 1700.0, 1600.0, pd.NA, 1500.0, 1550.0, 1600.0, 1650.0, 1700.0],
        }
    )

    monthly = resample_energy_balance(frame, "monthly")

    assert len(monthly) == 2
    assert pd.isna(monthly.iloc[0]["consumed_kcal"])
    assert monthly.iloc[1]["consumed_kcal"] == 8000.0


def test_energy_balance_chart_builds_diff_subplot() -> None:
    frame = pd.DataFrame(
        {
            "date": [date(2025, 1, 6), date(2025, 1, 13)],
            "spent_kcal": [500.0, 700.0],
            "consumed_kcal": [1800.0, 1600.0],
            "diff_kcal": [1300.0, 900.0],
        }
    )

    chart = EnergyBalanceChart().build(frame)
    spec = chart.to_dict()

    assert "vconcat" in spec
    assert len(spec["vconcat"]) == 2
    assert spec["resolve"]["scale"]["x"] == "shared"
    assert spec["vconcat"][0]["mark"]["type"] == "line"
    assert spec["vconcat"][1]["layer"][1]["mark"]["type"] == "line"
