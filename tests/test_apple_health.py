from pathlib import Path

from importers.apple_health import import_apple_health
from importers.db import connect, init_schema

FIXTURE = Path(__file__).parent / "fixtures" / "apple_health_sample.xml"


def test_import_apple_health_xml(tmp_path: Path) -> None:
    db_path = tmp_path / "health.duckdb"

    stats = import_apple_health(FIXTURE, db_path)

    assert stats.records == 3
    assert stats.workouts == 1
    assert stats.activity_summaries == 1
    assert stats.nutrition == 1

    conn = connect(db_path)
    try:
        record_count = conn.execute("SELECT COUNT(*) FROM apple_health_records").fetchone()[0]
        workout_count = conn.execute("SELECT COUNT(*) FROM apple_health_workouts").fetchone()[0]
        summary_count = conn.execute(
            "SELECT COUNT(*) FROM apple_health_activity_summaries"
        ).fetchone()[0]

        assert record_count == 3
        assert workout_count == 1
        assert summary_count == 1

        steps = conn.execute(
            """
            SELECT value
            FROM apple_health_records
            WHERE type = 'HKQuantityTypeIdentifierStepCount'
            """
        ).fetchone()[0]
        assert steps == 1234

        sleep = conn.execute(
            """
            SELECT value_text
            FROM apple_health_records
            WHERE type = 'HKCategoryTypeIdentifierSleepAnalysis'
            """
        ).fetchone()[0]
        assert sleep == "HKCategoryValueSleepAnalysisInBed"

        nutrition = conn.execute(
            """
            SELECT carbohydrates, fibre, protein, sodium, total_fat
            FROM apple_nutrition
            """
        ).fetchone()
        assert nutrition == (45.0, 8.0, 25.0, 640.0, 12.0)
    finally:
        conn.close()


def test_import_is_idempotent(tmp_path: Path) -> None:
    db_path = tmp_path / "health.duckdb"

    import_apple_health(FIXTURE, db_path)
    import_apple_health(FIXTURE, db_path)

    conn = connect(db_path)
    try:
        record_count = conn.execute("SELECT COUNT(*) FROM apple_health_records").fetchone()[0]
        assert record_count == 3
    finally:
        conn.close()


def test_replace_clears_existing_rows(tmp_path: Path) -> None:
    db_path = tmp_path / "health.duckdb"

    import_apple_health(FIXTURE, db_path)
    import_apple_health(FIXTURE, db_path, replace=True)

    conn = connect(db_path)
    try:
        import_count = conn.execute(
            "SELECT COUNT(*) FROM imports WHERE source = 'apple_health'"
        ).fetchone()[0]
        record_count = conn.execute("SELECT COUNT(*) FROM apple_health_records").fetchone()[0]

        assert import_count == 1
        assert record_count == 3
    finally:
        conn.close()


def test_init_schema_creates_tables(tmp_path: Path) -> None:
    db_path = tmp_path / "health.duckdb"
    conn = connect(db_path)
    try:
        init_schema(conn)
        tables = {
            row[0]
            for row in conn.execute(
                """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'main'
                """
            ).fetchall()
        }
        assert "apple_health_records" in tables
        assert "apple_health_workouts" in tables
        assert "apple_health_activity_summaries" in tables
        assert "apple_nutrition" in tables
    finally:
        conn.close()
