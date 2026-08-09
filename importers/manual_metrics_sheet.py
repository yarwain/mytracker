"""Load manual body measurements from a public Google Sheet CSV export."""

from __future__ import annotations

import re
from datetime import date, datetime
from io import StringIO
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

import pandas as pd

DEFAULT_SHEET_ID = "1J0eVC1AyV5Y4ooDRVrhFqdDZaH0UvB3TuQFNG_oEwwY"

DATE_COLUMNS = ("date", "дата")
METRIC_COLUMNS: dict[str, tuple[str, ...]] = {
    "neck": ("neck", "шея"),
    "waist": ("waist", "талия"),
    "hip": ("hip", "бедра", "hips"),
    "weight": ("weight", "body_mass", "body_mass_kg", "вес"),
}

DATE_FORMATS = ("%d.%m.%Y", "%Y-%m-%d", "%d/%m/%Y")

SheetMeasurement = tuple[date, dict[str, float]]


def google_sheet_csv_url(sheet_id: str, *, gid: str | None = None) -> str:
    """Build a public CSV export URL for a Google Sheet."""
    url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv"
    if gid is not None:
        url = f"{url}&gid={gid}"
    return url


def fetch_sheet_csv(sheet_id: str, *, gid: str | None = None) -> str:
    """Download CSV text from a public Google Sheet."""
    url = google_sheet_csv_url(sheet_id, gid=gid)
    try:
        with urlopen(url, timeout=30) as response:
            return response.read().decode("utf-8-sig")
    except HTTPError as exc:
        if exc.code in {401, 403}:
            msg = (
                "Could not read the Google Sheet. Make it public: "
                "Share → General access → Anyone with the link → Viewer."
            )
            raise PermissionError(msg) from exc
        raise
    except URLError as exc:
        raise ConnectionError(f"Could not download Google Sheet CSV from {url}") from exc


def _normalize_column(name: object) -> str:
    text = str(name).strip().lower()
    text = re.sub(r"\s+", "_", text)
    return text


def _resolve_column(columns: list[str], aliases: tuple[str, ...]) -> str | None:
    for alias in aliases:
        if alias in columns:
            return alias
    return None


def parse_measurement_date(value: object) -> date | None:
    """Parse a sheet date value into a date."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, date):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, pd.Timestamp):
        return value.date()

    text = str(value).strip()
    if not text:
        return None

    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue

    parsed = pd.to_datetime(text, dayfirst=True, errors="coerce")
    if pd.isna(parsed):
        return None
    return parsed.date()


def parse_measurement_value(value: object) -> float | None:
    """Parse a numeric measurement, skipping blank cells."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None

    text = str(value).strip().replace(",", ".")
    if not text:
        return None
    return float(text)


def load_measurements_from_csv(csv_text: str) -> list[SheetMeasurement]:
    """Parse measurement rows from CSV text."""
    frame = pd.read_csv(StringIO(csv_text))
    if frame.empty:
        return []

    frame.columns = [_normalize_column(column) for column in frame.columns]
    date_column = _resolve_column(list(frame.columns), DATE_COLUMNS)
    if date_column is None:
        msg = "CSV is missing required column: date. Expected a date header like date or дата."
        raise ValueError(msg)

    metric_columns = {
        metric_key: _resolve_column(list(frame.columns), aliases)
        for metric_key, aliases in METRIC_COLUMNS.items()
    }

    measurements: list[SheetMeasurement] = []
    for row in frame.itertuples(index=False):
        row_by_column = dict(zip(frame.columns, row, strict=True))
        measured_date = parse_measurement_date(row_by_column[date_column])
        if measured_date is None:
            continue

        values: dict[str, float] = {}
        for metric_key, column in metric_columns.items():
            if column is None:
                continue
            value = parse_measurement_value(row_by_column[column])
            if value is not None:
                values[metric_key] = value

        if not values:
            continue

        measurements.append((measured_date, values))

    measurements.sort(key=lambda item: item[0])
    return measurements


def load_measurements_from_sheet(
    sheet_id: str = DEFAULT_SHEET_ID,
    *,
    gid: str | None = None,
) -> list[SheetMeasurement]:
    """Fetch and parse measurements from a public Google Sheet."""
    csv_text = fetch_sheet_csv(sheet_id, gid=gid)
    return load_measurements_from_csv(csv_text)
