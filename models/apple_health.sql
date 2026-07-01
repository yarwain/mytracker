-- Apple Health tables (export.xml)

CREATE TABLE IF NOT EXISTS apple_health_records (
    import_id INTEGER NOT NULL,
    type VARCHAR NOT NULL,
    unit VARCHAR,
    value DOUBLE,
    value_text VARCHAR,
    source_name VARCHAR,
    source_version VARCHAR,
    device VARCHAR,
    creation_date TIMESTAMPTZ,
    start_date TIMESTAMPTZ NOT NULL,
    end_date TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS apple_health_workouts (
    import_id INTEGER NOT NULL,
    workout_activity_type VARCHAR NOT NULL,
    duration DOUBLE,
    duration_unit VARCHAR,
    total_distance DOUBLE,
    total_distance_unit VARCHAR,
    total_energy_burned DOUBLE,
    total_energy_burned_unit VARCHAR,
    source_name VARCHAR,
    source_version VARCHAR,
    device VARCHAR,
    creation_date TIMESTAMPTZ,
    start_date TIMESTAMPTZ NOT NULL,
    end_date TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS apple_health_activity_summaries (
    import_id INTEGER NOT NULL,
    summary_date DATE NOT NULL,
    active_energy_burned DOUBLE,
    active_energy_burned_goal DOUBLE,
    active_energy_burned_unit VARCHAR,
    apple_move_time DOUBLE,
    apple_move_time_goal DOUBLE,
    apple_exercise_time DOUBLE,
    apple_exercise_time_goal DOUBLE,
    apple_stand_hours DOUBLE,
    apple_stand_hours_goal DOUBLE
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_apple_health_workouts
    ON apple_health_workouts (workout_activity_type, start_date, end_date, source_name);

CREATE UNIQUE INDEX IF NOT EXISTS uq_apple_health_activity_summaries
    ON apple_health_activity_summaries (summary_date);

CREATE INDEX IF NOT EXISTS idx_apple_health_records_type_start
    ON apple_health_records (type, start_date);

CREATE INDEX IF NOT EXISTS idx_apple_health_workouts_start
    ON apple_health_workouts (start_date);

CREATE INDEX IF NOT EXISTS idx_apple_health_activity_summaries_date
    ON apple_health_activity_summaries (summary_date);
