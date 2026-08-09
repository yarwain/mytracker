from datetime import date, datetime

from app.config import BODY_MASS_METRIC, MANUAL_METRIC_BY_KEY
from app.database import Database
from app.repositories.body_mass_repository import BodyMassRepository
from importers.db import init_schema


def test_body_mass_repository_prefers_manual_weight_over_zepp(tmp_path) -> None:
    db_path = tmp_path / "health.duckdb"
    database = Database(db_path)
    with database.writable_connection() as conn:
        init_schema(conn)
        conn.execute(
            """
            INSERT INTO manual_metrics (measured_date, metric_name, value, unit)
            VALUES (?, ?, ?, ?)
            """,
            [date(2025, 6, 1), "weight", 54.5, "kg"],
        )
        conn.execute(
            """
            INSERT INTO apple_health_records (
                import_id, type, source_name, start_date, end_date, value, unit
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                1,
                BODY_MASS_METRIC.record_type,
                "Zepp Life",
                date(2025, 6, 1),
                date(2025, 6, 1),
                55.0,
                "kg",
            ],
        )
        conn.execute(
            """
            INSERT INTO apple_health_records (
                import_id, type, source_name, start_date, end_date, value, unit
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                1,
                BODY_MASS_METRIC.record_type,
                "Zepp Life",
                datetime(2025, 6, 2, 8, 0),
                datetime(2025, 6, 2, 8, 0),
                54.8,
                "kg",
            ],
        )

    repository = BodyMassRepository(database)
    frame = repository.load_daily()

    assert len(frame) == 2
    assert frame.iloc[0]["value"] == 54.5
    assert frame.iloc[0]["source_name"] == "manual"
    assert frame.iloc[1]["value"] == 54.8
    assert frame.iloc[1]["source_name"] == "Zepp Life"
    assert set(frame["label"]) == {"Body mass"}


def test_body_mass_repository_uses_manual_weight_only(tmp_path) -> None:
    db_path = tmp_path / "health.duckdb"
    database = Database(db_path)
    with database.writable_connection() as conn:
        init_schema(conn)
        conn.execute(
            """
            INSERT INTO manual_metrics (measured_date, metric_name, value, unit)
            VALUES (?, ?, ?, ?)
            """,
            [date(2025, 6, 3), "weight", 53.9, "kg"],
        )

    frame = BodyMassRepository(database).load_daily()
    assert len(frame) == 1
    assert frame.iloc[0]["value"] == 53.9
    assert frame.iloc[0]["label"] == MANUAL_METRIC_BY_KEY["weight"].label
