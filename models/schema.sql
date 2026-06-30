-- DuckDB schema for health tracking data

CREATE TABLE IF NOT EXISTS imports (
    id INTEGER PRIMARY KEY,
    source VARCHAR NOT NULL,
    imported_at TIMESTAMP DEFAULT current_timestamp,
    file_path VARCHAR
);
