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

## Database

The DuckDB file lives at `data/health.duckdb` (gitignored). Schema files live in `models/` and are applied automatically on import.
