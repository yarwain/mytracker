# mytracker

Personal health statistics from phone apps — import from Apple Health, Garmin, and FatSecret, store in DuckDB, and visualize with Streamlit.

## Project layout

```
mytracker/
├── app/                 # Streamlit app
├── data/                # Local data (ignored by Git)
│   └── health.duckdb    # DuckDB database
├── importers/           # Apple Health, Garmin, FatSecret
├── models/              # DuckDB SQL models
├── notebooks/           # Exploration
├── tests/
├── .gitignore
├── pyproject.toml
└── README.md
```

## Setup

Requires [uv](https://docs.astral.sh/uv/). Install all runtime and dev dependencies:

```bash
uv sync --all-extras
```

This creates `.venv` and installs the project in editable mode. Run commands with `uv run`, or activate the venv:

```bash
source .venv/bin/activate
```

## Run the app

```bash
uv run streamlit run app/main.py
```

## Import Apple Health

Export from the iPhone Health app (Settings → Health → Export All Health Data). Then import the zip or `export.xml`:

```bash
uv run import-apple-health ~/Downloads/export.zip
uv run import-apple-health ~/Downloads/export.zip --replace
```

The importer streams `export.xml` and loads these tables:

- `apple_health_records` — metrics such as steps, heart rate, sleep, and FatSecret dietary records
- `apple_health_workouts` — workouts with duration and distance
- `apple_health_activity_summaries` — daily Move / Exercise / Stand rings

Dietary data (carbohydrates, protein, fat, fibre, sodium, calories) is stored as individual rows in `apple_health_records`, same as other Apple Health quantity records.

Re-imports skip duplicate rows. Use `--replace` to wipe existing Apple Health data first.

## Seed manual metrics

Neck, waist, hip, and weight can be loaded from a public Google Sheet into the `manual_metrics` table. The script also calculates US Army body fat for dates with neck, waist, and hip.

The sheet must be readable without login: Share → General access → Anyone with the link → Viewer.

Expected columns (first row). Only `date` is required; other columns are optional per row:

| date | neck | waist | hip | weight |
|------|------|-------|-----|--------|
| 10.01.2026 | 31.5 | 70.5 | 96.5 | 54.2 |

Weight is in kg. Dates use `DD.MM.YYYY`. Rows without a date or without any measurement value are skipped. Re-imports upsert by date, so running the script again updates existing dates.

```bash
uv run python scripts/seed_manual_metrics.py
uv run python scripts/seed_manual_metrics.py --csv measurements.csv
uv run python scripts/seed_manual_metrics.py --gid 123456789
```

Use `--sheet-id` to load a different Google Sheet. Use `--csv` to load from a local file instead.

## Database

The DuckDB file lives at `data/health.duckdb` (gitignored). Schema files live in `models/` and are applied automatically on import.
