import logging
import time
from pathlib import Path

import duckdb
import pandas as pd

from importers.paths import DB_PATH, MODELS_DIR

logger = logging.getLogger(__name__)

NULLABLE_FLOAT_COLUMNS = {
    "value",
    "duration",
    "total_distance",
    "total_energy_burned",
    "active_energy_burned",
    "active_energy_burned_goal",
    "apple_move_time",
    "apple_move_time_goal",
    "apple_exercise_time",
    "apple_exercise_time_goal",
    "apple_stand_hours",
    "apple_stand_hours_goal",
    "carbohydrates",
    "fibre",
    "protein",
    "sodium",
    "total_fat",
}

TIMESTAMP_COLUMNS = {"start_date", "end_date", "creation_date", "summary_date"}


def connect(db_path: Path = DB_PATH) -> duckdb.DuckDBPyConnection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(str(db_path))


def init_schema(
    conn: duckdb.DuckDBPyConnection,
    models_dir: Path = MODELS_DIR,
) -> None:
    conn.execute((models_dir / "schema.sql").read_text())
    conn.execute((models_dir / "apple_health.sql").read_text())
    conn.execute(
        "ALTER TABLE apple_health_records ADD COLUMN IF NOT EXISTS value_text VARCHAR"
    )
    conn.execute((models_dir / "apple_nutrition.sql").read_text())
    conn.execute((models_dir / "manual_metrics.sql").read_text())
    conn.execute("DROP INDEX IF EXISTS uq_apple_health_records")
    conn.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_apple_health_records
        ON apple_health_records (
            type,
            start_date,
            end_date,
            coalesce(CAST(value AS VARCHAR), ''),
            coalesce(value_text, ''),
            coalesce(source_name, '')
        )
        """
    )
    logger.info("Schema ready (%s)", models_dir)


def start_import(
    conn: duckdb.DuckDBPyConnection,
    source: str,
    file_path: Path,
) -> int:
    row = conn.execute(
        """
        INSERT INTO imports (source, file_path)
        VALUES (?, ?)
        RETURNING id
        """,
        [source, str(file_path)],
    ).fetchone()
    import_id = int(row[0])
    logger.info("Started import_id=%s source=%s file=%s", import_id, source, file_path)
    return import_id


def _frame_from_rows(columns: list[str], rows: list[tuple]) -> pd.DataFrame:
    """Build a dataframe without turning NULL floats into NaN."""
    data: dict[str, list] = {column: [] for column in columns}
    for row in rows:
        for column, value in zip(columns, row, strict=True):
            data[column].append(value)

    frame = pd.DataFrame(data)
    for column in columns:
        if column in NULLABLE_FLOAT_COLUMNS:
            frame[column] = frame[column].astype(object)
    return frame


def _dedup_match(column: str) -> str:
    if column in TIMESTAMP_COLUMNS:
        return f"r.{column} IS NOT DISTINCT FROM b.{column}"
    if column == "value":
        return "coalesce(CAST(r.value AS VARCHAR), '') = coalesce(CAST(b.value AS VARCHAR), '')"
    return f"coalesce(r.{column}, '') = coalesce(b.{column}, '')"


def _dedup_partition(column: str) -> str:
    if column in TIMESTAMP_COLUMNS:
        return column
    if column == "value":
        return "coalesce(CAST(value AS VARCHAR), '')"
    return f"coalesce({column}, '')"


def bulk_insert_ignore(
    conn: duckdb.DuckDBPyConnection,
    table: str,
    columns: list[str],
    rows: list[tuple],
    *,
    dedup_columns: list[str] | None = None,
) -> int:
    """Insert a batch via a single INSERT ... SELECT FROM dataframe."""
    if not rows:
        return 0

    started = time.perf_counter()
    frame = _frame_from_rows(columns, rows)
    column_sql = ", ".join(columns)
    conn.register("_bulk_batch", frame)
    try:
        if dedup_columns:
            match_sql = " AND ".join(_dedup_match(column) for column in dedup_columns)
            existing_match_sql = match_sql.replace("b.", "deduped.")
            partition_sql = ", ".join(_dedup_partition(column) for column in dedup_columns)
            conn.execute(
                f"""
                INSERT INTO {table} ({column_sql})
                SELECT {column_sql}
                FROM (
                    SELECT
                        {column_sql},
                        row_number() OVER (
                            PARTITION BY {partition_sql}
                            ORDER BY import_id
                        ) AS _dedup_rn
                    FROM _bulk_batch
                ) AS deduped
                WHERE _dedup_rn = 1
                  AND NOT EXISTS (
                    SELECT 1
                    FROM {table} AS r
                    WHERE {existing_match_sql}
                )
                """
            )
        else:
            conn.execute(
                f"""
                INSERT OR IGNORE INTO {table} ({column_sql})
                SELECT {column_sql} FROM _bulk_batch
                """
            )
    finally:
        conn.unregister("_bulk_batch")
    elapsed = time.perf_counter() - started
    logger.info(
        "DuckDB bulk insert into %s: %s rows in %.2fs",
        table,
        f"{len(rows):,}",
        elapsed,
    )
    return len(rows)
