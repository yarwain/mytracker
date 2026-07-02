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
    assert monthly.iloc[0]["carb_kcal"] == pytest.approx(440.0)
    assert monthly.iloc[0]["calories"] == pytest.approx(1600.0)
