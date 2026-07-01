"""Repository for manually entered body measurements."""

from datetime import date

import pandas as pd

from app.calculators.us_army_body_fat import us_army_body_fat_percent_female
from app.config import (
    BODY_FAT_METRIC,
    ENTERABLE_METRIC_KEYS,
    MANUAL_CHART_METRICS,
    MANUAL_ENTRY_MEASUREMENTS,
    MANUAL_METRIC_BY_KEY,
    USER_HEIGHT_CM,
    ManualMetric,
)
from app.database import Database


class ManualMetricsRepository:
    """Load and store manual body measurements."""

    def __init__(self, database: Database | None = None) -> None:
        self._database = database or Database()

    def list_enterable_metrics(self) -> list[ManualMetric]:
        """Return metrics that can be entered manually."""
        return list(MANUAL_ENTRY_MEASUREMENTS)

    def list_chart_metrics(self) -> list[ManualMetric]:
        """Return metrics available for charts, including calculated body fat."""
        return list(MANUAL_CHART_METRICS)

    def upsert_measurement(
        self,
        measured_date: date,
        metric: ManualMetric,
        value: float,
        *,
        notes: str | None = None,
        refresh_body_fat: bool = True,
    ) -> None:
        """Insert or replace a measurement for the given date and metric."""
        self._database.execute(
            """
            INSERT INTO manual_metrics (measured_date, metric_name, value, unit, notes)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT (measured_date, metric_name) DO UPDATE SET
                value = excluded.value,
                unit = excluded.unit,
                notes = excluded.notes
            """,
            [measured_date, metric.key, value, metric.unit, notes],
        )
        if refresh_body_fat and metric.key in ENTERABLE_METRIC_KEYS:
            self.refresh_body_fat(measured_date)

    def upsert_measurements(
        self,
        measured_date: date,
        values: dict[str, float],
        *,
        notes: str | None = None,
    ) -> tuple[int, float | None]:
        """Save manual measurements and refresh derived body fat when possible."""
        saved = 0
        for metric_key, value in values.items():
            if metric_key not in ENTERABLE_METRIC_KEYS:
                continue
            metric = MANUAL_METRIC_BY_KEY[metric_key]
            self.upsert_measurement(
                measured_date,
                metric,
                value,
                notes=notes,
                refresh_body_fat=False,
            )
            saved += 1

        body_fat = self.refresh_body_fat(measured_date)
        return saved, body_fat

    def refresh_body_fat(self, measured_date: date) -> float | None:
        """Recalculate US Army body fat for a date when neck, waist, and hip exist."""
        frame = self._database.query(
            """
            SELECT metric_name, value
            FROM manual_metrics
            WHERE measured_date = ?
              AND metric_name IN ('neck', 'waist', 'hip')
            """,
            [measured_date],
        )
        if len(frame) != 3:
            self._delete_body_fat(measured_date)
            return None

        values = dict(zip(frame["metric_name"], frame["value"], strict=True))
        body_fat = us_army_body_fat_percent_female(
            neck_cm=values["neck"],
            waist_cm=values["waist"],
            hip_cm=values["hip"],
            height_cm=USER_HEIGHT_CM,
        )
        self.upsert_measurement(
            measured_date,
            BODY_FAT_METRIC,
            body_fat,
            notes="Calculated with US Army formula",
        )
        return body_fat

    def refresh_all_body_fat(self) -> int:
        """Recalculate body fat for every date with full circumference data."""
        dates = self._database.query(
            """
            SELECT measured_date
            FROM manual_metrics
            WHERE metric_name IN ('neck', 'waist', 'hip')
            GROUP BY measured_date
            HAVING COUNT(DISTINCT metric_name) = 3
            ORDER BY measured_date
            """
        )
        count = 0
        for measured_date in dates["measured_date"]:
            if self.refresh_body_fat(measured_date) is not None:
                count += 1
        return count

    def load_metrics(self, metrics: list[ManualMetric] | None = None) -> pd.DataFrame:
        """Return manual measurements in long format for charting."""
        selected = metrics or self.list_chart_metrics()
        if not selected:
            return pd.DataFrame(columns=["date", "value", "unit", "label", "reading_count"])

        keys = [metric.key for metric in selected]
        placeholders = ", ".join("?" for _ in keys)
        frame = self._database.query(
            f"""
            SELECT
                measured_date AS date,
                metric_name,
                value,
                unit
            FROM manual_metrics
            WHERE metric_name IN ({placeholders})
            ORDER BY measured_date
            """,
            keys,
        )
        if frame.empty:
            return pd.DataFrame(columns=["date", "value", "unit", "label", "reading_count"])

        label_by_key = {metric.key: metric.label for metric in MANUAL_CHART_METRICS}
        frame["label"] = frame["metric_name"].map(label_by_key)
        frame["reading_count"] = 1
        return frame.drop(columns="metric_name")

    def _delete_body_fat(self, measured_date: date) -> None:
        self._database.execute(
            """
            DELETE FROM manual_metrics
            WHERE measured_date = ?
              AND metric_name = 'body_fat'
            """,
            [measured_date],
        )
