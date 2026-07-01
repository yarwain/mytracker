"""Repository for Zepp Life metrics from Apple Health records."""

import pandas as pd

from app.config import MORNING_WINDOW, ZEPP_METRICS, ZEPP_SOURCE, HealthMetric
from app.database import Database


class ZeppRepository:
    """Load weekly aggregated metrics for Zepp Life."""

    def __init__(self, database: Database | None = None) -> None:
        self._database = database or Database()

    def list_available_metrics(self) -> list[HealthMetric]:
        """Return configured metrics that exist in the database for Zepp."""
        available_types = set(
            self._database.query(
                """
                SELECT DISTINCT type
                FROM apple_health_records
                WHERE source_name = ?
                  AND value IS NOT NULL
                """,
                [ZEPP_SOURCE],
            )["type"]
        )
        return [metric for metric in ZEPP_METRICS if metric.record_type in available_types]

    def _load_daily_metric(self, metric: HealthMetric) -> pd.DataFrame:
        """Load one daily aggregated metric series."""
        aggregation = "AVG(value)" if metric.aggregation == "avg" else "SUM(value)"
        morning_clause = ""
        parameters: list = [ZEPP_SOURCE, metric.record_type]

        if metric.morning_only:
            morning_clause = "AND EXTRACT(HOUR FROM start_date) BETWEEN ? AND ?"
            parameters.extend([MORNING_WINDOW.start_hour, MORNING_WINDOW.end_hour])

        return self._database.query(
            f"""
            SELECT
                CAST(start_date AS DATE) AS date,
                {aggregation} AS value,
                ANY_VALUE(unit) AS unit,
                COUNT(*) AS reading_count
            FROM apple_health_records
            WHERE source_name = ?
              AND type = ?
              AND value IS NOT NULL
              {morning_clause}
            GROUP BY 1
            ORDER BY 1
            """,
            parameters,
        )

    def load_weekly_metric(self, metric: HealthMetric) -> pd.DataFrame:
        """Load one weekly average metric series from daily morning readings."""
        daily = self._load_daily_metric(metric)
        if daily.empty:
            return daily

        daily = daily.copy()
        daily["date"] = pd.to_datetime(daily["date"])
        daily["week_start"] = daily["date"] - pd.to_timedelta(daily["date"].dt.dayofweek, unit="D")
        weekly = (
            daily.groupby("week_start", as_index=False)
            .agg(
                value=("value", "mean"),
                reading_count=("reading_count", "sum"),
                unit=("unit", "first"),
            )
            .rename(columns={"week_start": "date"})
            .sort_values("date")
        )
        weekly["date"] = weekly["date"].dt.date
        return weekly

    def load_selected_metrics(self, metrics: list[HealthMetric]) -> pd.DataFrame:
        """Load and combine multiple metrics into a long-format DataFrame."""
        frames: list[pd.DataFrame] = []
        for metric in metrics:
            frame = self.load_weekly_metric(metric)
            if frame.empty:
                continue
            frame["record_type"] = metric.record_type
            frame["label"] = metric.label
            frames.append(frame)

        if not frames:
            return pd.DataFrame(columns=["date", "value", "unit", "reading_count", "record_type", "label"])

        return pd.concat(frames, ignore_index=True)
