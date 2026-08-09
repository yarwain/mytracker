from datetime import datetime

from app.charts.aggregation import aggregate_weekly_average, resample_workout_breakdown
from app.config import (
    ACTIVITY_STEP_METRIC,
    ACTIVE_ENERGY_METRIC,
    GARMIN_SOURCE,
    POLAR_SOURCE,
)
from app.database import Database
from app.repositories.activity_repository import ActivityRepository, format_workout_activity
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


def _insert_steps(
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
            ACTIVITY_STEP_METRIC.record_type,
            source_name,
            start_date,
            start_date,
            value,
            "count",
        ],
    )


def _insert_workout(
    conn,
    *,
    start_date: datetime,
    source_name: str,
    duration: float,
    activity_type: str = "HKWorkoutActivityTypeRunning",
) -> None:
    conn.execute(
        """
        INSERT INTO apple_health_workouts (
            import_id,
            workout_activity_type,
            duration,
            duration_unit,
            source_name,
            start_date,
            end_date
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        [1, activity_type, duration, "min", source_name, start_date, start_date],
    )


def test_activity_repository_loads_polar_steps_and_workouts(tmp_path) -> None:
    db_path = tmp_path / "health.duckdb"
    database = Database(db_path)
    with database.writable_connection() as conn:
        init_schema(conn)
        for day in range(7):
            _insert_steps(
                conn,
                start_date=datetime(2025, 4, 7 + day, 12, 0),
                source_name=POLAR_SOURCE,
                value=1000.0 + day * 100,
            )
        _insert_workout(
            conn,
            start_date=datetime(2025, 4, 7, 18, 0),
            source_name=POLAR_SOURCE,
            duration=30.0,
        )
        _insert_workout(
            conn,
            start_date=datetime(2025, 4, 8, 18, 0),
            source_name=POLAR_SOURCE,
            duration=45.0,
            activity_type="HKWorkoutActivityTypeCycling",
        )

    repository = ActivityRepository(database)

    assert repository.has_data() is True
    assert repository.resolve_workout_source() == POLAR_SOURCE

    steps = repository.load_steps()
    assert len(steps) == 7
    assert steps.iloc[0]["value"] == 1000.0
    assert steps.iloc[0]["source_name"] == POLAR_SOURCE
    assert repository.describe_steps_sources(steps) == POLAR_SOURCE

    workouts = repository.load_workout_breakdown()
    assert set(workouts["activity"]) == {"Running", "Cycling"}
    assert workouts.loc[workouts["activity"] == "Running", "workout_count"].tolist() == [1.0]

    weekly_steps = aggregate_weekly_average(steps)
    assert len(weekly_steps) == 1
    assert weekly_steps.iloc[0]["value"] == 1300.0

    weekly_workouts = resample_workout_breakdown(workouts, "weekly")
    running_week = weekly_workouts[
        (weekly_workouts["activity"] == "Running")
        & (weekly_workouts["date"] == datetime(2025, 4, 7).date())
    ]
    assert running_week.iloc[0]["workout_count"] == 1.0


def test_activity_repository_uses_available_source_when_no_conflict(tmp_path) -> None:
    db_path = tmp_path / "health.duckdb"
    database = Database(db_path)
    with database.writable_connection() as conn:
        init_schema(conn)
        _insert_steps(
            conn,
            start_date=datetime(2025, 4, 7, 12, 0),
            source_name="iPhone",
            value=5000.0,
        )

    repository = ActivityRepository(database)
    steps = repository.load_steps()

    assert repository.has_data() is True
    assert len(steps) == 1
    assert steps.iloc[0]["source_name"] == "iPhone"
    assert steps.iloc[0]["value"] == 5000.0


def test_activity_repository_uses_all_non_conflicting_sources(tmp_path) -> None:
    db_path = tmp_path / "health.duckdb"
    database = Database(db_path)
    with database.writable_connection() as conn:
        init_schema(conn)
        _insert_steps(
            conn,
            start_date=datetime(2025, 4, 7, 12, 0),
            source_name="iPhone",
            value=5000.0,
        )
        _insert_steps(
            conn,
            start_date=datetime(2025, 4, 8, 12, 0),
            source_name=POLAR_SOURCE,
            value=6000.0,
        )
        _insert_steps(
            conn,
            start_date=datetime(2025, 4, 9, 12, 0),
            source_name=GARMIN_SOURCE,
            value=7000.0,
        )

    repository = ActivityRepository(database)
    steps = repository.load_steps()

    assert len(steps) == 3
    assert steps.iloc[0]["source_name"] == "iPhone"
    assert steps.iloc[1]["source_name"] == POLAR_SOURCE
    assert steps.iloc[2]["source_name"] == GARMIN_SOURCE
    assert repository.describe_steps_sources(steps) == "Garmin Connect, Polar Flow, iPhone"


def test_activity_repository_prefers_polar_on_same_day_conflict(tmp_path) -> None:
    db_path = tmp_path / "health.duckdb"
    database = Database(db_path)
    with database.writable_connection() as conn:
        init_schema(conn)
        _insert_steps(
            conn,
            start_date=datetime(2025, 4, 7, 12, 0),
            source_name="iPhone",
            value=9000.0,
        )
        _insert_steps(
            conn,
            start_date=datetime(2025, 4, 7, 12, 0),
            source_name=GARMIN_SOURCE,
            value=8000.0,
        )
        _insert_steps(
            conn,
            start_date=datetime(2025, 4, 7, 12, 0),
            source_name=POLAR_SOURCE,
            value=7000.0,
        )

    repository = ActivityRepository(database)
    steps = repository.load_steps()

    assert len(steps) == 1
    assert steps.iloc[0]["source_name"] == POLAR_SOURCE
    assert steps.iloc[0]["value"] == 7000.0


def test_activity_repository_prefers_garmin_over_apple_health_on_same_day(tmp_path) -> None:
    db_path = tmp_path / "health.duckdb"
    database = Database(db_path)
    with database.writable_connection() as conn:
        init_schema(conn)
        _insert_steps(
            conn,
            start_date=datetime(2025, 4, 7, 12, 0),
            source_name="iPhone",
            value=9000.0,
        )
        _insert_steps(
            conn,
            start_date=datetime(2025, 4, 7, 12, 0),
            source_name=GARMIN_SOURCE,
            value=8000.0,
        )

    repository = ActivityRepository(database)
    steps = repository.load_steps()

    assert len(steps) == 1
    assert steps.iloc[0]["source_name"] == GARMIN_SOURCE
    assert steps.iloc[0]["value"] == 8000.0


def test_activity_repository_loads_energy_with_polar_priority(tmp_path) -> None:
    db_path = tmp_path / "health.duckdb"
    database = Database(db_path)
    with database.writable_connection() as conn:
        init_schema(conn)
        _insert_energy(
            conn,
            start_date=datetime(2025, 4, 7, 12, 0),
            source_name=GARMIN_SOURCE,
            value=700.0,
        )
        _insert_energy(
            conn,
            start_date=datetime(2025, 4, 7, 18, 0),
            source_name=POLAR_SOURCE,
            value=650.0,
        )
        _insert_energy(
            conn,
            start_date=datetime(2025, 4, 8, 12, 0),
            source_name=GARMIN_SOURCE,
            value=600.0,
        )

    repository = ActivityRepository(database)
    energy = repository.load_daily_energy_burned()

    assert len(energy) == 2
    assert energy.iloc[0]["source_name"] == POLAR_SOURCE
    assert energy.iloc[0]["value"] == 650.0
    assert energy.iloc[1]["source_name"] == GARMIN_SOURCE
    assert energy.iloc[1]["value"] == 600.0


def test_format_workout_activity() -> None:
    assert format_workout_activity("HKWorkoutActivityTypeRunning") == "Running"
    assert format_workout_activity("HKWorkoutActivityTypeHighIntensityIntervalTraining") == (
        "High Intensity Interval Training"
    )
