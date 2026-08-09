from datetime import date

from app.calculators.us_army_body_fat import us_army_body_fat_percent_female
from app.config import BODY_FAT_METRIC, MANUAL_METRIC_BY_KEY, USER_HEIGHT_CM
from app.database import Database
from app.repositories.manual_metrics_repository import ManualMetricsRepository
from importers.db import init_schema


def test_manual_metrics_upsert_and_load(tmp_path) -> None:
    db_path = tmp_path / "health.duckdb"
    database = Database(db_path)
    with database.writable_connection() as conn:
        init_schema(conn)

    repository = ManualMetricsRepository(database)
    measurements = {
        "neck": 38.0,
        "waist": 82.5,
        "hip": 98.0,
    }
    repository.upsert_measurements(date(2024, 6, 1), measurements)

    frame = repository.load_metrics()
    assert len(frame) == 4
    assert set(frame["label"]) == {
        "Neck size",
        "Waist size",
        "Hip size",
        "Body fat (US Army)",
    }

    expected_body_fat = us_army_body_fat_percent_female(
        neck_cm=measurements["neck"],
        waist_cm=measurements["waist"],
        hip_cm=measurements["hip"],
        height_cm=USER_HEIGHT_CM,
    )
    body_fat = frame.loc[frame["label"] == "Body fat (US Army)", "value"].iloc[0]
    assert body_fat == expected_body_fat

    repository.upsert_measurement(date(2024, 6, 1), MANUAL_METRIC_BY_KEY["waist"], 81.0)
    frame = repository.load_metrics([MANUAL_METRIC_BY_KEY["waist"], BODY_FAT_METRIC])
    assert frame.loc[frame["label"] == "Waist size", "value"].iloc[-1] == 81.0

    updated_body_fat = frame.loc[frame["label"] == "Body fat (US Army)", "value"].iloc[-1]
    assert updated_body_fat == us_army_body_fat_percent_female(
        neck_cm=measurements["neck"],
        waist_cm=81.0,
        hip_cm=measurements["hip"],
        height_cm=USER_HEIGHT_CM,
    )


def test_manual_metrics_upsert_additional_measurements(tmp_path) -> None:
    db_path = tmp_path / "health.duckdb"
    database = Database(db_path)
    with database.writable_connection() as conn:
        init_schema(conn)

    repository = ManualMetricsRepository(database)
    repository.upsert_measurements(
        date(2024, 6, 2),
        {"thigh": 58.0, "arm": 28.0, "belly": 82.0},
    )

    frame = repository.load_metrics()
    labels = set(frame["label"])
    assert {"Thigh size", "Arm size", "Belly size"}.issubset(labels)
