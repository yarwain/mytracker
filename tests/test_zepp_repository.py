from datetime import datetime

import pandas as pd

from app.config import ZEPP_METRICS, ZEPP_SOURCE
from app.database import Database
from app.repositories.zepp_repository import ZeppRepository
from importers.db import init_schema


def _insert_reading(
    conn,
    *,
    start_date: datetime,
    record_type: str,
    value: float,
) -> None:
    conn.execute(
        """
        INSERT INTO apple_health_records (
            import_id, type, source_name, start_date, end_date, value, unit
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        [1, record_type, ZEPP_SOURCE, start_date, start_date, value, "kg"],
    )


def test_zepp_repository_aggregates_weekly(tmp_path) -> None:
    db_path = tmp_path / "health.duckdb"
    database = Database(db_path)
    with database.writable_connection() as conn:
        init_schema(conn)
        metric = ZEPP_METRICS[0]
        for day in range(7):
            _insert_reading(
                conn,
                start_date=datetime(2025, 3, 10 + day, 8, 0),
                record_type=metric.record_type,
                value=50.0 + day,
            )
        _insert_reading(
            conn,
            start_date=datetime(2025, 3, 17, 8, 0),
            record_type=metric.record_type,
            value=60.0,
        )

    repository = ZeppRepository(database)
    daily = repository._load_daily_metric(metric)
    weekly = repository.load_weekly_metric(metric)

    assert len(daily) == 8
    assert len(weekly) == 2
    assert weekly.iloc[0]["date"] == datetime(2025, 3, 10).date()
    assert weekly.iloc[0]["value"] == 53.0
    assert weekly.iloc[1]["value"] == 60.0
