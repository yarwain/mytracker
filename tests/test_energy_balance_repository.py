from datetime import datetime

import pandas as pd

from app.config import (
    ACTIVE_ENERGY_METRIC,
    CALORIES_CONSUMED_METRIC,
    FATSECRET_SOURCE,
    GARMIN_SOURCE,
    POLAR_SOURCE,
)
from app.database import Database
from app.repositories.energy_balance_repository import EnergyBalanceRepository
from importers.db import init_schema


def _insert_energy(
    conn,
    *,
    start_date: datetime,
    source_name: str,
    value: float,
) -> None:
    conn.execute(
        """
        INSERT INTO apple_health_records (
            import_id, type, source_name, start_date, end_date, value, unit
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        [
            1,
            ACTIVE_ENERGY_METRIC.record_type,
            source_name,
            start_date,
            start_date,
            value,
            "kcal",
        ],
    )


def _insert_calories(
    conn,
    *,
    start_date: datetime,
    source_name: str,
    value: float,
) -> None:
    conn.execute(
        """
        INSERT INTO apple_health_records (
            import_id, type, source_name, start_date, end_date, value, unit
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        [
            1,
            CALORIES_CONSUMED_METRIC.record_type,
            source_name,
            start_date,
            start_date,
            value,
            "kcal",
        ],
    )


def test_energy_balance_repository_merges_spent_and_consumed(tmp_path) -> None:
    db_path = tmp_path / "health.duckdb"
    database = Database(db_path)
    with database.writable_connection() as conn:
        init_schema(conn)
        _insert_energy(
            conn,
            start_date=datetime(2025, 5, 1, 12, 0),
            source_name=POLAR_SOURCE,
            value=500.0,
        )
        _insert_calories(
            conn,
            start_date=datetime(2025, 5, 1, 12, 0),
            source_name=FATSECRET_SOURCE,
            value=1800.0,
        )
        _insert_energy(
            conn,
            start_date=datetime(2025, 5, 2, 12, 0),
            source_name=GARMIN_SOURCE,
            value=600.0,
        )

    repository = EnergyBalanceRepository(database)
    balance = repository.load_daily_balance()

    assert len(balance) == 2
    day_one = balance.loc[balance["date"] == datetime(2025, 5, 1).date()].iloc[0]
    assert day_one["spent_kcal"] == 500.0
    assert day_one["consumed_kcal"] == 1800.0
    assert day_one["diff_kcal"] == 1300.0
    assert day_one["spent_source"] == POLAR_SOURCE

    day_two = balance.loc[balance["date"] == datetime(2025, 5, 2).date()].iloc[0]
    assert day_two["spent_kcal"] == 600.0
    assert pd.isna(day_two["consumed_kcal"])


def test_energy_balance_repository_uses_selected_meal_log_sources(tmp_path) -> None:
    db_path = tmp_path / "health.duckdb"
    database = Database(db_path)
    with database.writable_connection() as conn:
        init_schema(conn)
        _insert_calories(
            conn,
            start_date=datetime(2025, 5, 4, 12, 0),
            source_name="Lifesum",
            value=1900.0,
        )

    repository = EnergyBalanceRepository(database)
    assert repository.load_daily_balance(sources=["FatSecret"]).empty
    balance = repository.load_daily_balance(sources=["Lifesum"])
    assert balance.iloc[0]["consumed_kcal"] == 1900.0


def test_energy_balance_repository_prefers_polar_on_same_day(tmp_path) -> None:
    db_path = tmp_path / "health.duckdb"
    database = Database(db_path)
    with database.writable_connection() as conn:
        init_schema(conn)
        _insert_energy(
            conn,
            start_date=datetime(2025, 5, 3, 12, 0),
            source_name=GARMIN_SOURCE,
            value=700.0,
        )
        _insert_energy(
            conn,
            start_date=datetime(2025, 5, 3, 18, 0),
            source_name=POLAR_SOURCE,
            value=650.0,
        )

    balance = EnergyBalanceRepository(database).load_daily_balance()
    row = balance.iloc[0]
    assert row["spent_kcal"] == 650.0
    assert row["spent_source"] == POLAR_SOURCE
