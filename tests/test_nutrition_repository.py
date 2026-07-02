from datetime import datetime

import pytest

from app.config import MIN_DAILY_CALORIES, NUTRITION_METRICS
from app.database import Database
from app.repositories.nutrition_repository import NutritionRepository
from importers.db import init_schema


def _insert_record(
    conn,
    *,
    record_type: str,
    start_date: datetime,
    source_name: str,
    value: float,
    unit: str,
) -> None:
    conn.execute(
        """
        INSERT INTO apple_health_records (
            import_id,
            type,
            unit,
            value,
            source_name,
            start_date,
            end_date
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        [1, record_type, unit, value, source_name, start_date, start_date],
    )


def _insert_meal(
    conn,
    *,
    start_date: datetime,
    source_name: str,
    carbohydrates: float,
    protein: float,
    total_fat: float,
    calories: float,
) -> None:
    _insert_record(
        conn,
        record_type="HKQuantityTypeIdentifierDietaryCarbohydrates",
        start_date=start_date,
        source_name=source_name,
        value=carbohydrates,
        unit="g",
    )
    _insert_record(
        conn,
        record_type="HKQuantityTypeIdentifierDietaryProtein",
        start_date=start_date,
        source_name=source_name,
        value=protein,
        unit="g",
    )
    _insert_record(
        conn,
        record_type="HKQuantityTypeIdentifierDietaryFatTotal",
        start_date=start_date,
        source_name=source_name,
        value=total_fat,
        unit="g",
    )
    _insert_record(
        conn,
        record_type="HKQuantityTypeIdentifierDietaryEnergyConsumed",
        start_date=start_date,
        source_name=source_name,
        value=calories,
        unit="kcal",
    )


def test_nutrition_repository_weekly_macro_average(tmp_path) -> None:
    db_path = tmp_path / "health.duckdb"
    database = Database(db_path)
    with database.writable_connection() as conn:
        init_schema(conn)
        _insert_meal(
            conn,
            start_date=datetime(2024, 6, 3, 12, 0),
            source_name="FatSecret",
            carbohydrates=200.0,
            protein=100.0,
            total_fat=50.0,
            calories=1500.0,
        )
        _insert_meal(
            conn,
            start_date=datetime(2024, 6, 4, 12, 0),
            source_name="FatSecret",
            carbohydrates=10.0,
            protein=5.0,
            total_fat=2.0,
            calories=500.0,
        )
        _insert_meal(
            conn,
            start_date=datetime(2024, 6, 5, 12, 0),
            source_name="Lifesum",
            carbohydrates=150.0,
            protein=80.0,
            total_fat=40.0,
            calories=1400.0,
        )

    repository = NutritionRepository(database)
    carbs_metric = next(
        metric for metric in NUTRITION_METRICS if metric.record_type.endswith("Carbohydrates")
    )

    weekly = repository.load_weekly_metric(carbs_metric)
    fatsecret_only = repository.load_weekly_metric(carbs_metric, sources=["FatSecret"])

    assert len(weekly) == 1
    assert weekly.iloc[0]["date"] == datetime(2024, 6, 3).date()
    assert weekly.iloc[0]["value"] == pytest.approx((200.0 + 10.0 + 150.0) / 3)
    assert weekly.iloc[0]["day_count"] == 3

    assert len(fatsecret_only) == 1
    assert fatsecret_only.iloc[0]["value"] == pytest.approx((200.0 + 10.0) / 2)
    assert fatsecret_only.iloc[0]["day_count"] == 2

    assert repository.list_sources() == ["FatSecret", "Lifesum"]


def test_weekly_average_calories_excludes_low_intake_days(tmp_path) -> None:
    db_path = tmp_path / "health.duckdb"
    database = Database(db_path)
    with database.writable_connection() as conn:
        init_schema(conn)
        _insert_meal(
            conn,
            start_date=datetime(2024, 6, 3, 12, 0),
            source_name="FatSecret",
            carbohydrates=200.0,
            protein=100.0,
            total_fat=50.0,
            calories=1500.0,
        )
        _insert_meal(
            conn,
            start_date=datetime(2024, 6, 4, 12, 0),
            source_name="FatSecret",
            carbohydrates=10.0,
            protein=5.0,
            total_fat=2.0,
            calories=500.0,
        )
        _insert_meal(
            conn,
            start_date=datetime(2024, 6, 5, 12, 0),
            source_name="FatSecret",
            carbohydrates=150.0,
            protein=80.0,
            total_fat=40.0,
            calories=1200.0,
        )

    repository = NutritionRepository(database)
    calories_metric = next(
        metric for metric in NUTRITION_METRICS if metric.record_type.endswith("EnergyConsumed")
    )

    daily = repository._load_daily_metric(calories_metric)
    weekly = repository.load_weekly_metric(calories_metric)

    assert daily.loc[daily["date"].astype(str) == "2024-06-04", "value"].iloc[0] == 500.0
    assert 500.0 < MIN_DAILY_CALORIES
    assert len(weekly) == 1
    assert weekly.iloc[0]["value"] == pytest.approx((1500.0 + 1200.0) / 2)
    assert weekly.iloc[0]["day_count"] == 2


def test_macro_calorie_breakdown_filters_and_computes_kcal(tmp_path) -> None:
    db_path = tmp_path / "health.duckdb"
    database = Database(db_path)
    with database.writable_connection() as conn:
        init_schema(conn)
        _insert_meal(
            conn,
            start_date=datetime(2024, 6, 3, 12, 0),
            source_name="FatSecret",
            carbohydrates=100.0,
            protein=50.0,
            total_fat=20.0,
            calories=1500.0,
        )
        _insert_meal(
            conn,
            start_date=datetime(2024, 6, 4, 12, 0),
            source_name="FatSecret",
            carbohydrates=10.0,
            protein=5.0,
            total_fat=2.0,
            calories=500.0,
        )

    repository = NutritionRepository(database)
    breakdown = repository.load_macro_calorie_breakdown()

    assert len(breakdown) == 1
    row = breakdown.iloc[0]
    assert row["carbohydrates"] == 100.0
    assert row["carb_kcal"] == 400.0
    assert row["protein_kcal"] == 200.0
    assert row["fat_kcal"] == 180.0
    assert row["calories"] == 1500.0
