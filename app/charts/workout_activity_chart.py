"""Grouped bar chart for workout activity summaries."""

import altair as alt
import pandas as pd

from app.charts.aggregation import Period
from app.config import WORKOUT_MEASURE_COUNT, WORKOUT_MEASURE_DURATION


class WorkoutActivityChart:
    """Build grouped bars for workout count or duration by activity."""

    def __init__(self, *, height: int = 420) -> None:
        self._height = height

    def build(
        self,
        df: pd.DataFrame,
        *,
        period: Period = "weekly",
        measure: str = WORKOUT_MEASURE_COUNT,
    ) -> alt.Chart:
        """Plot selected activities as grouped columns per period."""
        if df.empty:
            return alt.Chart(pd.DataFrame({"date": [], "value": []})).mark_point()

        plot_df = df.copy()
        plot_df["date"] = pd.to_datetime(plot_df["date"])
        value_column = "workout_count" if measure == WORKOUT_MEASURE_COUNT else "total_duration"
        plot_df["value"] = plot_df[value_column]
        y_title = "Workouts" if measure == WORKOUT_MEASURE_COUNT else "Minutes"
        date_title = "Month" if period == "monthly" else "Date"

        return (
            alt.Chart(plot_df)
            .mark_bar()
            .encode(
                x=alt.X("date:T", title=date_title),
                xOffset=alt.XOffset("activity:N"),
                y=alt.Y("value:Q", title=y_title, scale=alt.Scale(zero=True)),
                color=alt.Color("activity:N", title="Activity"),
                tooltip=[
                    alt.Tooltip("date:T", title=date_title),
                    alt.Tooltip("activity:N", title="Activity"),
                    alt.Tooltip("value:Q", title=y_title, format=",.0f"),
                ],
            )
            .properties(height=self._height)
        )
