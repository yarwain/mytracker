from datetime import datetime, timezone

from importers.db import bulk_insert_ignore, connect, init_schema

RECORD_COLUMNS = [
    "import_id",
    "type",
    "unit",
    "value",
    "value_text",
    "source_name",
    "source_version",
    "device",
    "creation_date",
    "start_date",
    "end_date",
]


def test_bulk_insert_skips_existing_null_value_rows(tmp_path) -> None:
    db_path = tmp_path / "health.duckdb"
    conn = connect(db_path)
    init_schema(conn)

    start = datetime(2024, 12, 10, 20, 40, tzinfo=timezone.utc)
    end = datetime(2024, 12, 10, 22, 30, tzinfo=timezone.utc)
    row = (
        1,
        "HKCategoryTypeIdentifierSleepAnalysis",
        None,
        None,
        "HKCategoryValueSleepAnalysisAsleepUnspecified",
        "Polar Flow",
        "1.0",
        None,
        start,
        start,
        end,
    )

    bulk_insert_ignore(
        conn,
        "apple_health_records",
        RECORD_COLUMNS,
        [row],
        dedup_columns=["type", "start_date", "end_date", "value", "value_text", "source_name"],
    )
    bulk_insert_ignore(
        conn,
        "apple_health_records",
        RECORD_COLUMNS,
        [row],
        dedup_columns=["type", "start_date", "end_date", "value", "value_text", "source_name"],
    )

    count = conn.execute("SELECT COUNT(*) FROM apple_health_records").fetchone()[0]
    assert count == 1
    conn.close()


def test_bulk_insert_dedupes_rows_within_batch(tmp_path) -> None:
    db_path = tmp_path / "health.duckdb"
    conn = connect(db_path)
    init_schema(conn)

    start = datetime(2024, 12, 10, 20, 40, tzinfo=timezone.utc)
    end = datetime(2024, 12, 10, 22, 30, tzinfo=timezone.utc)
    row = (
        1,
        "HKCategoryTypeIdentifierSleepAnalysis",
        None,
        None,
        "HKCategoryValueSleepAnalysisAsleepUnspecified",
        "Polar Flow",
        "1.0",
        None,
        start,
        start,
        end,
    )

    bulk_insert_ignore(
        conn,
        "apple_health_records",
        RECORD_COLUMNS,
        [row, row],
        dedup_columns=["type", "start_date", "end_date", "value", "value_text", "source_name"],
    )

    count = conn.execute("SELECT COUNT(*) FROM apple_health_records").fetchone()[0]
    assert count == 1
    conn.close()
