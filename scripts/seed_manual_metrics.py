"""Seed manual body measurements from a public Google Sheet into DuckDB."""

from __future__ import annotations

import argparse
from pathlib import Path

from app.database import Database
from app.repositories.manual_metrics_repository import ManualMetricsRepository
from importers.manual_metrics_sheet import (
    DEFAULT_SHEET_ID,
    SheetMeasurement,
    load_measurements_from_csv,
    load_measurements_from_sheet,
)


def seed_manual_metrics(
    measurements: list[SheetMeasurement],
    database: Database | None = None,
) -> tuple[int, int]:
    """Insert measurements. Returns number of dates written and body-fat rows."""
    database = database or Database()
    database.ensure_schema()
    repository = ManualMetricsRepository(database)

    for measured_date, values in measurements:
        repository.upsert_measurements(measured_date, values)

    body_fat_count = repository.refresh_all_body_fat()
    return len(measurements), body_fat_count


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Seed manual body measurements from a public Google Sheet CSV export",
    )
    parser.add_argument(
        "--sheet-id",
        default=DEFAULT_SHEET_ID,
        help=f"Google Sheet ID (default: {DEFAULT_SHEET_ID})",
    )
    parser.add_argument(
        "--gid",
        default=None,
        help="Worksheet gid when the sheet has multiple tabs",
    )
    parser.add_argument(
        "--csv",
        type=Path,
        default=None,
        help="Load from a local CSV file instead of Google Sheets",
    )
    args = parser.parse_args()

    if args.csv is not None:
        measurements = load_measurements_from_csv(args.csv.read_text(encoding="utf-8-sig"))
        source = str(args.csv)
    else:
        measurements = load_measurements_from_sheet(args.sheet_id, gid=args.gid)
        source = f"Google Sheet {args.sheet_id}"

    if not measurements:
        raise SystemExit(f"No measurement rows found in {source}.")

    date_count, body_fat_count = seed_manual_metrics(measurements)
    print(f"Seeded manual measurements for {date_count} dates from {source}.")
    print(f"Calculated US Army body fat for {body_fat_count} dates.")


if __name__ == "__main__":
    main()
