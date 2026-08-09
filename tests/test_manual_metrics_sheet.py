from datetime import date
from pathlib import Path

import pytest

from importers.manual_metrics_sheet import (
    google_sheet_csv_url,
    load_measurements_from_csv,
    parse_measurement_date,
)

FIXTURE = Path(__file__).parent / "fixtures" / "manual_metrics.csv"


def test_google_sheet_csv_url() -> None:
    assert google_sheet_csv_url("abc123") == (
        "https://docs.google.com/spreadsheets/d/abc123/export?format=csv"
    )
    assert google_sheet_csv_url("abc123", gid="0") == (
        "https://docs.google.com/spreadsheets/d/abc123/export?format=csv&gid=0"
    )


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("10.01.2026", date(2026, 1, 10)),
        ("2026-01-10", date(2026, 1, 10)),
        (date(2026, 1, 10), date(2026, 1, 10)),
    ],
)
def test_parse_measurement_date(value, expected) -> None:
    assert parse_measurement_date(value) == expected


def test_load_measurements_from_csv_fixture() -> None:
    measurements = load_measurements_from_csv(FIXTURE.read_text(encoding="utf-8"))
    assert measurements == [
        (date(2026, 1, 10), {"neck": 31.5, "waist": 70.5, "hip": 96.5, "weight": 54.2}),
        (date(2026, 1, 18), {"neck": 31.0, "waist": 70.0, "hip": 95.5}),
    ]


def test_load_measurements_from_csv_weight_only_row() -> None:
    measurements = load_measurements_from_csv(
        "date,weight\n10.01.2026,54.2\n11.01.2026,\n",
    )
    assert measurements == [(date(2026, 1, 10), {"weight": 54.2})]


def test_load_measurements_from_csv_parses_thigh_arm_belly() -> None:
    measurements = load_measurements_from_csv(
        "date,thigh,arm,belly\n10.01.2026,58.0,28.0,82.0\n",
    )
    assert measurements == [
        (date(2026, 1, 10), {"thigh": 58.0, "arm": 28.0, "belly": 82.0}),
    ]


def test_load_measurements_from_csv_requires_date_column() -> None:
    with pytest.raises(ValueError, match="missing required column: date"):
        load_measurements_from_csv("weight,notes\n70,test\n")
