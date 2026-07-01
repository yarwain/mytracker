-- Manual body measurements entered in the Streamlit app

CREATE SEQUENCE IF NOT EXISTS manual_metrics_id_seq START 1;

CREATE TABLE IF NOT EXISTS manual_metrics (
    id INTEGER PRIMARY KEY DEFAULT nextval('manual_metrics_id_seq'),
    measured_date DATE NOT NULL,
    metric_name VARCHAR NOT NULL,
    value DOUBLE NOT NULL,
    unit VARCHAR NOT NULL DEFAULT 'cm',
    notes VARCHAR,
    created_at TIMESTAMP DEFAULT current_timestamp
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_manual_metrics_date_name
    ON manual_metrics (measured_date, metric_name);

CREATE INDEX IF NOT EXISTS idx_manual_metrics_name_date
    ON manual_metrics (metric_name, measured_date);
