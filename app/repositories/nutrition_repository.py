"""Repository for nutrition data from Apple Health dietary records."""

import pandas as pd

from app.config import (
    CALORIES_CONSUMED_METRIC,
    FATSECRET_SOURCE,
    MIN_DAILY_CALORIES,
    NUTRITION_METRICS,
    NUTRITION_RECORD_TYPES,
    NutritionMetric,
)
from app.database import Database


class NutritionRepository:
    """Load weekly average nutrition metrics from apple_health_records."""

    def __init__(self, database: Database | None = None) -> None:
        self._database = database or Database()

    def list_sources(self) -> list[str]:
        """Return nutrition sources present in the database."""
        placeholders = ", ".join("?" for _ in NUTRITION_RECORD_TYPES)
        frame = self._database.query(
            f"""
            SELECT DISTINCT source_name
            FROM apple_health_records
            WHERE type IN ({placeholders})
              AND source_name IS NOT NULL
            ORDER BY source_name
            """,
            list(NUTRITION_RECORD_TYPES),
        )
        if frame.empty:
            return []
        return frame["source_name"].tolist()

    def list_available_metrics(self) -> list[NutritionMetric]:
        """Return configured metrics that exist in the database."""
        placeholders = ", ".join("?" for _ in NUTRITION_RECORD_TYPES)
        available_types = set(
            self._database.query(
                f"""
                SELECT DISTINCT type
                FROM apple_health_records
                WHERE type IN ({placeholders})
                  AND value IS NOT NULL
                """,
                list(NUTRITION_RECORD_TYPES),
            )["type"]
        )
        return [metric for metric in NUTRITION_METRICS if metric.record_type in available_types]

    def _source_clause(self, sources: list[str] | None) -> tuple[str, list]:
        if not sources:
            return "", []
        placeholders = ", ".join("?" for _ in sources)
        return f"AND source_name IN ({placeholders})", list(sources)

    def _load_daily_metric(
        self,
        metric: NutritionMetric,
        *,
        sources: list[str] | None = None,
    ) -> pd.DataFrame:
        """Load one daily total for a dietary record type."""
        source_clause, source_params = self._source_clause(sources)
        parameters = [metric.record_type, *source_params]
        return self._database.query(
            f"""
            SELECT
                CAST(start_date AS DATE) AS date,
                SUM(value) AS value,
                ANY_VALUE(unit) AS unit,
                COUNT(*) AS reading_count
            FROM apple_health_records
            WHERE type = ?
              AND value IS NOT NULL
              {source_clause}
            GROUP BY 1
            ORDER BY 1
            """,
            parameters,
        )

    @staticmethod
    def _align_daily_to_logged_days(
        daily: pd.DataFrame,
        logged_dates: pd.DataFrame,
        metric: NutritionMetric,
    ) -> pd.DataFrame:
        """Align one metric to logged meal days, using zero when a valid day has no rows."""
        base = logged_dates[["date"]].drop_duplicates().copy()
        if base.empty:
            return pd.DataFrame(columns=["date", "value", "unit", "reading_count"])

        if daily.empty:
            aligned = base.copy()
            aligned["value"] = 0.0
            aligned["unit"] = metric.unit
            aligned["reading_count"] = 0
            return aligned

        aligned = base.merge(daily, on="date", how="left")
        aligned["value"] = aligned["value"].fillna(0.0)
        aligned["unit"] = aligned["unit"].fillna(metric.unit)
        aligned["reading_count"] = aligned["reading_count"].fillna(0).astype(int)
        return aligned

    def _logged_days(self, *, sources: list[str] | None = None) -> pd.DataFrame:
        logged = self.load_macro_calorie_breakdown(sources=sources)
        if logged.empty:
            return pd.DataFrame(columns=["date"])
        return logged[["date"]]

    @staticmethod
    def _aggregate_weekly_average(daily: pd.DataFrame) -> pd.DataFrame:
        """Average daily values within each Monday-based week."""
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
                day_count=("value", "count"),
            )
            .rename(columns={"week_start": "date"})
            .sort_values("date")
        )
        weekly["date"] = weekly["date"].dt.date
        return weekly

    def load_weekly_metric(
        self,
        metric: NutritionMetric,
        *,
        sources: list[str] | None = None,
    ) -> pd.DataFrame:
        """Load weekly average per logged meal day for one nutrition metric."""
        logged_dates = self._logged_days(sources=sources)
        if logged_dates.empty:
            return pd.DataFrame(columns=["date", "value", "unit", "reading_count", "day_count"])

        daily = self._load_daily_metric(metric, sources=sources)
        daily = self._align_daily_to_logged_days(daily, logged_dates, metric)
        weekly = self._aggregate_weekly_average(daily)
        if weekly.empty:
            return weekly
        weekly["unit"] = metric.unit
        return weekly

    def load_daily_metrics_aligned(
        self,
        metrics: list[NutritionMetric],
        *,
        sources: list[str] | None = None,
    ) -> pd.DataFrame:
        """Load daily metrics aligned to logged meal days in long format."""
        logged_dates = self._logged_days(sources=sources)
        if logged_dates.empty:
            return pd.DataFrame(
                columns=["date", "value", "unit", "reading_count", "record_type", "label"]
            )

        frames: list[pd.DataFrame] = []
        for metric in metrics:
            daily = self._load_daily_metric(metric, sources=sources)
            aligned = self._align_daily_to_logged_days(daily, logged_dates, metric)
            aligned["record_type"] = metric.record_type
            aligned["label"] = metric.label
            frames.append(aligned)

        return pd.concat(frames, ignore_index=True)

    def load_selected_metrics(
        self,
        metrics: list[NutritionMetric],
        *,
        sources: list[str] | None = None,
    ) -> pd.DataFrame:
        """Load and combine multiple nutrition metrics into a long-format DataFrame."""
        daily = self.load_daily_metrics_aligned(metrics, sources=sources)
        if daily.empty:
            return pd.DataFrame(
                columns=[
                    "date",
                    "value",
                    "unit",
                    "reading_count",
                    "day_count",
                    "record_type",
                    "label",
                ]
            )

        weekly_frames: list[pd.DataFrame] = []
        for metric in metrics:
            metric_daily = daily[daily["label"] == metric.label].copy()
            weekly = self._aggregate_weekly_average(metric_daily)
            if weekly.empty:
                continue
            weekly["record_type"] = metric.record_type
            weekly["label"] = metric.label
            weekly["unit"] = metric.unit
            weekly_frames.append(weekly)

        if not weekly_frames:
            return pd.DataFrame(
                columns=[
                    "date",
                    "value",
                    "unit",
                    "reading_count",
                    "day_count",
                    "record_type",
                    "label",
                ]
            )

        return pd.concat(weekly_frames, ignore_index=True)

    def load_daily_calories_consumed(
        self,
        *,
        sources: list[str] | None = None,
    ) -> pd.DataFrame:
        """Load daily logged calorie totals for one or more nutrition sources."""
        daily = self._load_daily_metric(CALORIES_CONSUMED_METRIC, sources=sources)
        if daily.empty:
            return daily

        daily = daily.copy()
        daily["label"] = CALORIES_CONSUMED_METRIC.label
        return daily

    def has_fatsecret_calories(self) -> bool:
        """Return whether FatSecret calorie records exist."""
        count = self._database.query(
            """
            SELECT 1 AS present
            FROM apple_health_records
            WHERE type = ?
              AND value IS NOT NULL
              AND source_name = ?
            LIMIT 1
            """,
            [CALORIES_CONSUMED_METRIC.record_type, FATSECRET_SOURCE],
        )
        return not count.empty

    def load_macro_calorie_breakdown(self, *, sources: list[str] | None = None) -> pd.DataFrame:
        """Load daily macro grams and logged calories for stacked calorie charts."""
        source_clause, source_params = self._source_clause(sources)
        frame = self._database.query(
            f"""
            SELECT
                CAST(start_date AS DATE) AS date,
                SUM(
                    CASE
                        WHEN type = 'HKQuantityTypeIdentifierDietaryCarbohydrates'
                        THEN value ELSE 0
                    END
                ) AS carbohydrates,
                SUM(
                    CASE
                        WHEN type = 'HKQuantityTypeIdentifierDietaryProtein'
                        THEN value ELSE 0
                    END
                ) AS protein,
                SUM(
                    CASE
                        WHEN type = 'HKQuantityTypeIdentifierDietaryFatTotal'
                        THEN value ELSE 0
                    END
                ) AS total_fat,
                SUM(
                    CASE
                        WHEN type = 'HKQuantityTypeIdentifierDietaryEnergyConsumed'
                        THEN value ELSE 0
                    END
                ) AS calories
            FROM apple_health_records
            WHERE type IN (
                'HKQuantityTypeIdentifierDietaryCarbohydrates',
                'HKQuantityTypeIdentifierDietaryProtein',
                'HKQuantityTypeIdentifierDietaryFatTotal',
                'HKQuantityTypeIdentifierDietaryEnergyConsumed'
            )
              {source_clause}
            GROUP BY 1
            HAVING calories >= ?
            ORDER BY 1
            """,
            [*source_params, MIN_DAILY_CALORIES],
        )
        if frame.empty:
            return frame

        frame["carb_kcal"] = frame["carbohydrates"] * 4
        frame["protein_kcal"] = frame["protein"] * 4
        frame["fat_kcal"] = frame["total_fat"] * 9
        return frame
