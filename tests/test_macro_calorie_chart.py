from datetime import date

import pandas as pd

from app.charts.macro_calorie_chart import MacroCalorieChart


def test_macro_calorie_chart_stacks_body_mass_subplot() -> None:
    macro_df = pd.DataFrame(
        {
            "date": [date(2025, 1, 6), date(2025, 1, 13)],
            "carbohydrates": [100.0, 120.0],
            "protein": [80.0, 90.0],
            "total_fat": [50.0, 60.0],
            "calories": [1500.0, 1700.0],
            "carb_kcal": [400.0, 480.0],
            "protein_kcal": [320.0, 360.0],
            "fat_kcal": [450.0, 540.0],
        }
    )
    body_mass_df = pd.DataFrame(
        {
            "date": [date(2025, 1, 6), date(2025, 1, 13), date(2025, 1, 20)],
            "value": [62.0, 61.5, 61.0],
            "unit": ["kg", "kg", "kg"],
            "label": ["Body mass", "Body mass", "Body mass"],
        }
    )

    chart = MacroCalorieChart().build(macro_df, body_mass_df=body_mass_df)
    spec = chart.to_dict()

    assert "vconcat" in spec
    assert len(spec["vconcat"]) == 2
    assert spec["vconcat"][0]["layer"][1]["mark"]["type"] == "line"
    assert spec["vconcat"][1]["layer"][1]["mark"]["type"] == "line"
    assert spec["resolve"]["scale"]["x"] == "shared"
    assert spec["vconcat"][0]["height"] == 180
    assert spec["vconcat"][1]["height"] == 100
