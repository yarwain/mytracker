"""Repository for nutrition data from Apple Health dietary records."""

import pandas as pd

from app.config import MIN_DAILY_CALORIES, NUTRITION_METRICS, NUTRITION_RECORD_TYPES, NutritionMetric
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
    def _filter_daily_for_metric(daily: pd.DataFrame, metric: NutritionMetric) -> pd.DataFrame:
        """Apply metric-specific day filters before weekly aggregation."""
        if daily.empty:
            return daily

        values = daily["value"].fillna(0)
        if metric.min_daily_calories is not None:
            return daily.loc[values >= metric.min_daily_calories].copy()
        return daily.loc[values > 0].copy()

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
        """Load weekly average per logged day for one nutrition metric."""
        daily = self._load_daily_metric(metric, sources=sources)
        daily = self._filter_daily_for_metric(daily, metric)
        weekly = self._aggregate_weekly_average(daily)
        if weekly.empty:
            return weekly
        if "unit" not in weekly.columns:
            weekly["unit"] = metric.unit
        return weekly

    def load_selected_metrics(
        self,
        metrics: list[NutritionMetric],
        *,
        sources: list[str] | None = None,
    ) -> pd.DataFrame:
        """Load and combine multiple nutrition metrics into a long-format DataFrame."""
        frames: list[pd.DataFrame] = []
        for metric in metrics:
            frame = self.load_weekly_metric(metric, sources=sources)
            if frame.empty:
                continue
            frame["record_type"] = metric.record_type
            frame["label"] = metric.label
            frames.append(frame)

        if not frames:
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

        return pd.concat(frames, ignore_index=True)

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
