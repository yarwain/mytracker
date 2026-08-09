"""Repository for activity data from Apple Health."""

import re

import pandas as pd

from app.config import (
    ACTIVITY_STEP_METRIC,
    ACTIVE_ENERGY_METRIC,
    GARMIN_SOURCE,
    POLAR_SOURCE,
    PREFERRED_ACTIVITY_SOURCES,
)
from app.database import Database


def format_workout_activity(activity_type: str) -> str:
    """Turn HealthKit workout identifiers into readable labels."""
    label = activity_type.removeprefix("HKWorkoutActivityType")
    return re.sub(r"(?<=[a-z])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])", " ", label)


class ActivityRepository:
    """Load steps and workouts from Apple Health records."""

    def __init__(self, database: Database | None = None) -> None:
        self._database = database or Database()

    def has_data(self) -> bool:
        """Return whether any steps or workouts exist."""
        return self._has_any_steps() or self.resolve_workout_source() is not None

    def resolve_workout_source(self) -> str | None:
        """Pick the highest-priority source that has workout data."""
        for source in PREFERRED_ACTIVITY_SOURCES:
            if self._has_workouts(source):
                return source
        return self._best_fallback_workout_source()

    def load_steps(self) -> pd.DataFrame:
        """Load daily step totals, resolving source conflicts per day."""
        by_source = self._load_daily_steps_by_source()
        if by_source.empty:
            return pd.DataFrame(
                columns=["date", "value", "unit", "reading_count", "label", "source_name"]
            )

        resolved = self._resolve_daily_by_source(by_source)
        resolved = resolved.copy()
        resolved["label"] = ACTIVITY_STEP_METRIC.label
        return resolved.sort_values("date").reset_index(drop=True)

    def load_daily_energy_burned(self) -> pd.DataFrame:
        """Load daily active energy from Polar/Garmin, preferring Polar on conflicts."""
        by_source = self._load_daily_energy_by_source()
        if by_source.empty:
            return pd.DataFrame(
                columns=["date", "value", "unit", "reading_count", "label", "source_name"]
            )

        resolved = self._resolve_daily_by_source(by_source)
        resolved = resolved.copy()
        resolved["label"] = ACTIVE_ENERGY_METRIC.label
        return resolved.sort_values("date").reset_index(drop=True)

    def has_energy_data(self) -> bool:
        """Return whether any Polar or Garmin active energy records exist."""
        count = self._database.query(
            """
            SELECT 1 AS present
            FROM apple_health_records
            WHERE type = ?
              AND value IS NOT NULL
              AND source_name IN (?, ?)
            LIMIT 1
            """,
            [ACTIVE_ENERGY_METRIC.record_type, POLAR_SOURCE, GARMIN_SOURCE],
        )
        return not count.empty

    @staticmethod
    def describe_steps_sources(steps_df: pd.DataFrame) -> str:
        """Return a readable summary of step sources used in the chart data."""
        if steps_df.empty:
            return "unknown source"
        sources = sorted(steps_df["source_name"].unique().tolist())
        if len(sources) == 1:
            return sources[0]
        return ", ".join(sources)

    def load_workout_breakdown(self) -> pd.DataFrame:
        """Load daily workout count and duration per activity type."""
        source = self.resolve_workout_source()
        if source is None:
            return pd.DataFrame(
                columns=[
                    "date",
                    "activity_type",
                    "activity",
                    "workout_count",
                    "total_duration",
                    "source_name",
                ]
            )

        daily = self._load_daily_workout_breakdown(source)
        if daily.empty:
            return pd.DataFrame(
                columns=[
                    "date",
                    "activity_type",
                    "activity",
                    "workout_count",
                    "total_duration",
                    "source_name",
                ]
            )

        daily = daily.copy()
        daily["activity"] = daily["activity_type"].map(format_workout_activity)
        daily["source_name"] = source
        return daily

    def list_workout_activities(self) -> list[str]:
        """Return sorted readable activity labels present in the data."""
        breakdown = self.load_workout_breakdown()
        if breakdown.empty:
            return []
        return sorted(breakdown["activity"].unique().tolist())

    def load_workout_sessions(self) -> pd.DataFrame:
        """Load individual workout sessions for the resolved source."""
        source = self.resolve_workout_source()
        if source is None:
            return pd.DataFrame(
                columns=[
                    "start_date",
                    "workout_activity_type",
                    "duration",
                    "duration_unit",
                    "total_distance",
                    "total_distance_unit",
                ]
            )

        return self._database.query(
            """
            SELECT
                start_date,
                workout_activity_type,
                duration,
                duration_unit,
                total_distance,
                total_distance_unit
            FROM apple_health_workouts
            WHERE source_name = ?
            ORDER BY start_date
            """,
            [source],
        )

    def _has_any_steps(self) -> bool:
        count = self._database.query(
            """
            SELECT 1 AS present
            FROM apple_health_records
            WHERE type = ?
              AND value IS NOT NULL
            LIMIT 1
            """,
            [ACTIVITY_STEP_METRIC.record_type],
        )
        return not count.empty

    def _has_workouts(self, source_name: str) -> bool:
        count = self._database.query(
            """
            SELECT 1 AS present
            FROM apple_health_workouts
            WHERE source_name = ?
            LIMIT 1
            """,
            [source_name],
        )
        return not count.empty

    def _resolve_daily_by_source(self, by_source: pd.DataFrame) -> pd.DataFrame:
        """Pick one source per day, using priority only when several sources overlap."""
        rows: list[pd.Series] = []
        for _, group in by_source.groupby("date", sort=True):
            if len(group) == 1:
                rows.append(group.iloc[0])
                continue
            rows.append(self._pick_preferred_source(group))

        return pd.DataFrame(rows)

    def _pick_preferred_source(self, group: pd.DataFrame) -> pd.Series:
        """Resolve same-day values from Polar, then Garmin, then the highest fallback."""
        for source in PREFERRED_ACTIVITY_SOURCES:
            match = group[group["source_name"] == source]
            if not match.empty:
                return match.iloc[0]

        fallback = group.sort_values("value", ascending=False).iloc[0]
        return fallback

    def _pick_conflicting_steps(self, group: pd.DataFrame) -> pd.Series:
        """Resolve same-day steps from Polar, then Garmin, then Apple Health."""
        return self._pick_preferred_source(group)

    def _load_daily_energy_by_source(self) -> pd.DataFrame:
        return self._database.query(
            """
            SELECT
                CAST(start_date AS DATE) AS date,
                source_name,
                SUM(value) AS value,
                ANY_VALUE(unit) AS unit,
                COUNT(*) AS reading_count
            FROM apple_health_records
            WHERE type = ?
              AND value IS NOT NULL
              AND source_name IN (?, ?)
            GROUP BY 1, 2
            ORDER BY 1, 2
            """,
            [ACTIVE_ENERGY_METRIC.record_type, POLAR_SOURCE, GARMIN_SOURCE],
        )

    def _load_daily_steps_by_source(self) -> pd.DataFrame:
        return self._database.query(
            """
            SELECT
                CAST(start_date AS DATE) AS date,
                source_name,
                SUM(value) AS value,
                ANY_VALUE(unit) AS unit,
                COUNT(*) AS reading_count
            FROM apple_health_records
            WHERE type = ?
              AND value IS NOT NULL
            GROUP BY 1, 2
            ORDER BY 1, 2
            """,
            [ACTIVITY_STEP_METRIC.record_type],
        )

    def _best_fallback_workout_source(self) -> str | None:
        result = self._database.query(
            """
            SELECT source_name
            FROM apple_health_workouts
            WHERE source_name NOT IN (?, ?)
            GROUP BY source_name
            ORDER BY COUNT(*) DESC
            LIMIT 1
            """,
            [POLAR_SOURCE, GARMIN_SOURCE],
        )
        if result.empty:
            return None
        return str(result.iloc[0]["source_name"])

    def _load_daily_workout_breakdown(self, source_name: str) -> pd.DataFrame:
        return self._database.query(
            """
            SELECT
                CAST(start_date AS DATE) AS date,
                workout_activity_type AS activity_type,
                COUNT(*) AS workout_count,
                SUM(duration) AS total_duration
            FROM apple_health_workouts
            WHERE source_name = ?
            GROUP BY 1, 2
            ORDER BY 1, 2
            """,
            [source_name],
        )
