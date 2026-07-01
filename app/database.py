"""DuckDB access helpers for the Streamlit application."""

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import duckdb
import pandas as pd

from importers.db import init_schema
from importers.paths import DB_PATH


class Database:
    """Wrapper around a DuckDB database file."""

    def __init__(self, db_path: Path = DB_PATH) -> None:
        self.db_path = db_path

    @property
    def exists(self) -> bool:
        """Return whether the database file is present on disk."""
        return self.db_path.exists()

    def ensure_schema(self) -> None:
        """Apply SQL schema files, including tables added after first import."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self.writable_connection() as conn:
            init_schema(conn)

    def query(self, sql: str, parameters: list | None = None) -> pd.DataFrame:
        """Run a read-only SQL query and return the result as a DataFrame."""
        with self.readonly_connection() as conn:
            return conn.execute(sql, parameters or []).df()

    def execute(self, sql: str, parameters: list | None = None) -> None:
        """Run a write SQL statement."""
        with self.writable_connection() as conn:
            conn.execute(sql, parameters or [])

    @contextmanager
    def readonly_connection(self) -> Iterator[duckdb.DuckDBPyConnection]:
        """Open a read-only DuckDB connection."""
        conn = duckdb.connect(str(self.db_path), read_only=True)
        try:
            yield conn
        finally:
            conn.close()

    @contextmanager
    def writable_connection(self) -> Iterator[duckdb.DuckDBPyConnection]:
        """Open a writable DuckDB connection."""
        conn = duckdb.connect(str(self.db_path))
        try:
            yield conn
        finally:
            conn.close()

    @contextmanager
    def connection(self) -> Iterator[duckdb.DuckDBPyConnection]:
        """Open a read-only connection for backward compatibility."""
        with self.readonly_connection() as conn:
            yield conn
