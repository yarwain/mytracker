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

## Database

The DuckDB file lives at `data/health.duckdb` (gitignored). Apply the initial schema:

```bash
uv run duckdb data/health.duckdb < models/schema.sql
```
