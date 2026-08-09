from datetime import datetime

import pandas as pd
import pytest

from app.charts.aggregation import aggregate_monthly_average, aggregate_weekly_average


def test_aggregate_weekly_average_groups_by_label() -> None:
    frame = pd.DataFrame(
        {
            "date": [
                datetime(2024, 6, 3),
                datetime(2024, 6, 5),
                datetime(2024, 6, 10),
            ],
            "label": ["Carbohydrates", "Carbohydrates", "Protein"],
            "value": [100.0, 120.0, 50.0],
            "unit": ["g", "g", "g"],
        }
    )

    weekly = aggregate_weekly_average(frame)

    carbs = weekly.loc[weekly["label"] == "Carbohydrates"]
    assert len(carbs) == 1
    assert carbs.iloc[0]["date"] == datetime(2024, 6, 3).date()
    assert carbs.iloc[0]["value"] == pytest.approx(110.0)


def test_aggregate_monthly_average_groups_by_label() -> None:
    frame = pd.DataFrame(
        {
            "date": [
                datetime(2024, 6, 3),
                datetime(2024, 6, 17),
                datetime(2024, 7, 1),
            ],
            "label": ["Calories", "Calories", "Calories"],
            "value": [1800.0, 2000.0, 1500.0],
            "unit": ["kcal", "kcal", "kcal"],
        }
    )

    monthly = aggregate_monthly_average(frame)

    assert len(monthly) == 2
    june = monthly.loc[monthly["date"] == datetime(2024, 6, 1).date(), "value"].iloc[0]
    july = monthly.loc[monthly["date"] == datetime(2024, 7, 1).date(), "value"].iloc[0]
    assert june == pytest.approx(1900.0)
    assert july == pytest.approx(1500.0)


def test_resample_breakdown_monthly_average() -> None:
    from app.charts.aggregation import resample_breakdown

    frame = pd.DataFrame(
        {
            "date": [datetime(2024, 6, 3), datetime(2024, 6, 10)],
            "carbohydrates": [100.0, 120.0],
            "protein": [50.0, 70.0],
            "total_fat": [20.0, 30.0],
            "calories": [1500.0, 1700.0],
            "carb_kcal": [400.0, 480.0],
            "protein_kcal": [200.0, 280.0],
            "fat_kcal": [180.0, 270.0],
        }
    )

    monthly = resample_breakdown(frame, "monthly")

    assert len(monthly) == 1
    assert pd.isna(monthly.iloc[0]["carb_kcal"])
    assert pd.isna(monthly.iloc[0]["calories"])


def test_resample_breakdown_keeps_periods_but_masks_low_coverage_weeks() -> None:
    from app.charts.aggregation import resample_breakdown

    frame = pd.DataFrame(
        {
            "date": [
                datetime(2024, 6, 3),
                datetime(2024, 6, 4),
                datetime(2024, 6, 5),
                datetime(2024, 6, 10),
                datetime(2024, 6, 11),
                datetime(2024, 6, 12),
                datetime(2024, 6, 13),
            ],
            "carbohydrates": [100.0, 110.0, 120.0, 90.0, 95.0, 100.0, 105.0],
            "protein": [50.0, 55.0, 60.0, 40.0, 42.0, 44.0, 46.0],
            "total_fat": [20.0, 22.0, 24.0, 18.0, 19.0, 20.0, 21.0],
            "calories": [1500.0, 1550.0, 1600.0, 1400.0, 1450.0, 1500.0, 1550.0],
            "carb_kcal": [400.0, 440.0, 480.0, 360.0, 380.0, 400.0, 420.0],
            "protein_kcal": [200.0, 220.0, 240.0, 160.0, 168.0, 176.0, 184.0],
            "fat_kcal": [180.0, 198.0, 216.0, 162.0, 171.0, 180.0, 189.0],
        }
    )

    weekly = resample_breakdown(frame, "weekly")

    assert len(weekly) == 2
    assert pd.isna(weekly.iloc[0]["calories"])
    assert weekly.iloc[1]["calories"] == pytest.approx(1475.0)


def test_resample_breakdown_weekly_average_uses_six_of_seven_logged_days() -> None:
    from app.charts.aggregation import resample_breakdown

    dates = [datetime(2024, 6, 3 + day) for day in range(7)]
    calories = [1500.0 if day != 2 else 500.0 for day in range(7)]
    carbs = [float(100 + day) for day in range(7)]

    frame = pd.DataFrame(
        {
            "date": dates,
            "carbohydrates": carbs,
            "protein": [50.0] * 7,
            "total_fat": [20.0] * 7,
            "calories": calories,
            "carb_kcal": [400.0] * 7,
            "protein_kcal": [200.0] * 7,
            "fat_kcal": [180.0] * 7,
        }
    )
    frame = frame[frame["calories"] >= 1500.0]

    weekly = resample_breakdown(frame, "weekly")

    assert len(weekly) == 1
    expected = sum(carbs[i] for i in range(7) if i != 2) / 6
    assert weekly.iloc[0]["carbohydrates"] == pytest.approx(expected)


def test_resample_breakdown_monthly_average_uses_only_logged_days() -> None:
    from app.charts.aggregation import resample_breakdown

    dates = [datetime(2024, 6, day) for day in [1, 2, 3, 4, 5, 10]]
    calories = [1500.0] * 5 + [500.0]
    carbs = [100.0, 101.0, 102.0, 103.0, 104.0, 999.0]

    frame = pd.DataFrame(
        {
            "date": dates,
            "carbohydrates": carbs,
            "protein": [50.0] * 6,
            "total_fat": [20.0] * 6,
            "calories": calories,
            "carb_kcal": [400.0] * 6,
            "protein_kcal": [200.0] * 6,
            "fat_kcal": [180.0] * 6,
        }
    )
    frame = frame[frame["calories"] >= 1500.0]

    monthly = resample_breakdown(frame, "monthly")

    assert len(monthly) == 1
    assert monthly.iloc[0]["carbohydrates"] == pytest.approx(102.0)
