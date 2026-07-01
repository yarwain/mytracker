-- DuckDB schema for health tracking data

CREATE SEQUENCE IF NOT EXISTS imports_id_seq START 1;

CREATE TABLE IF NOT EXISTS imports (
    id INTEGER PRIMARY KEY DEFAULT nextval('imports_id_seq'),
    source VARCHAR NOT NULL,
    imported_at TIMESTAMP DEFAULT current_timestamp,
    file_path VARCHAR
);
