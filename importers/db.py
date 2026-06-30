from pathlib import Path

import duckdb

from importers.paths import DB_PATH, MODELS_DIR


def connect(db_path: Path = DB_PATH) -> duckdb.DuckDBPyConnection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(str(db_path))


def init_schema(
    conn: duckdb.DuckDBPyConnection,
    models_dir: Path = MODELS_DIR,
) -> None:
    for sql_file in ("schema.sql", "apple_health.sql"):
        sql = (models_dir / sql_file).read_text()
        conn.execute(sql)


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
    return int(row[0])
