from datetime import date

import pandas as pd

from app.charts.macro_calorie_chart import MacroCalorieChart


def test_macro_calorie_chart_layers_body_mass_above_calories() -> None:
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
            "date": [date(2025, 1, 6), date(2025, 1, 13)],
            "value": [62.0, 61.5],
            "unit": ["kg", "kg"],
            "label": ["Body mass", "Body mass"],
        }
    )

    chart = MacroCalorieChart().build(macro_df, body_mass_df=body_mass_df)
    spec = chart.to_dict()

    assert spec["layer"][0]["layer"][1]["mark"]["type"] == "line"
    assert spec["layer"][1]["mark"]["type"] == "line"
    assert spec["layer"][2]["mark"]["type"] == "line"
    assert spec["resolve"]["scale"]["y"] == "independent"
