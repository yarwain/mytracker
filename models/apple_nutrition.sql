-- Apple Health nutrition (dietary records from export.xml)

CREATE TABLE IF NOT EXISTS apple_nutrition (
    import_id INTEGER NOT NULL,
    source_name VARCHAR,
    source_version VARCHAR,
    creation_date TIMESTAMPTZ,
    start_date TIMESTAMPTZ NOT NULL,
    end_date TIMESTAMPTZ,
    carbohydrates DOUBLE,
    carbohydrates_unit VARCHAR,
    fibre DOUBLE,
    fibre_unit VARCHAR,
    protein DOUBLE,
    protein_unit VARCHAR,
    sodium DOUBLE,
    sodium_unit VARCHAR,
    total_fat DOUBLE,
    total_fat_unit VARCHAR
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_apple_nutrition
    ON apple_nutrition (start_date, end_date, source_name);

CREATE INDEX IF NOT EXISTS idx_apple_nutrition_start
    ON apple_nutrition (start_date);
