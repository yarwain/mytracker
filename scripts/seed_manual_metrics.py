"""Seed historical manual body measurements into DuckDB."""

from __future__ import annotations

from datetime import date, datetime

from app.database import Database
from app.repositories.manual_metrics_repository import ManualMetricsRepository

# Oldest first; later rows overwrite the same date on upsert.
# date (DD.MM.YYYY), neck, waist, hip
MEASUREMENTS: list[tuple[str, float, float, float]] = [
    ("10.01.2026", 31.5, 70.5, 96.5),
    ("18.01.2026", 31.0, 70.0, 95.5),
    ("26.01.2026", 31.0, 70.0, 95.5),
    ("01.02.2026", 31.5, 68.5, 95.0),
    ("14.02.2026", 31.5, 69.0, 95.0),
    ("21.02.2026", 31.0, 70.0, 95.5),
    ("03.03.2026", 31.0, 70.0, 95.0),
    ("08.03.2026", 31.5, 70.0, 95.0),
    ("16.03.2026", 31.5, 70.0, 95.0),
    ("21.03.2026", 31.5, 70.0, 96.0),
    ("07.04.2026", 31.5, 69.0, 96.0),
    ("13.04.2026", 31.5, 68.5, 95.0),
    ("20.04.2026", 31.5, 69.0, 95.0),
    ("27.04.2026", 31.5, 69.0, 95.5),
    ("18.05.2026", 31.5, 69.5, 97.0),
    ("31.05.2026", 31.5, 70.5, 96.5),
    ("06.06.2026", 31.5, 70.0, 96.0),
    ("14.06.2026", 31.0, 69.0, 94.5),
    ("21.06.2026", 31.0, 69.0, 95.0),
    ("27.06.2026", 31.0, 69.0, 96.0),
]


def parse_date(value: str) -> date:
    """Parse a DD.MM.YYYY date string."""
    return datetime.strptime(value, "%d.%m.%Y").date()


def seed_manual_metrics(database: Database | None = None) -> tuple[int, int]:
    """Insert seed measurements. Returns number of dates written."""
    database = database or Database()
    database.ensure_schema()
    repository = ManualMetricsRepository(database)

    for date_text, neck, waist, hip in MEASUREMENTS:
        measured_date = parse_date(date_text)
        repository.upsert_measurements(
            measured_date,
            {"neck": neck, "waist": waist, "hip": hip},
        )

    body_fat_count = repository.refresh_all_body_fat()
    return len(MEASUREMENTS), body_fat_count


def main() -> None:
    date_count, body_fat_count = seed_manual_metrics()
    print(f"Seeded manual measurements for {date_count} dates.")
    print(f"Calculated US Army body fat for {body_fat_count} dates.")


if __name__ == "__main__":
    main()
