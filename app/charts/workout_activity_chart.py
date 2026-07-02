"""Grouped bar chart for workout activity summaries."""

import altair as alt
import pandas as pd

from app.charts.aggregation import Period
from app.charts.theme import SERIES_COLORS, date_encoding, date_tooltip_title, finalize, numeric_axis
from app.config import WORKOUT_MEASURE_COUNT, WORKOUT_MEASURE_DURATION


class WorkoutActivityChart:
    """Build grouped bars for workout count or duration by activity."""

    def build(
        self,
        df: pd.DataFrame,
        *,
        period: Period = "weekly",
        measure: str = WORKOUT_MEASURE_COUNT,
    ) -> alt.Chart:
        """Plot selected activities as grouped columns per period."""
        if df.empty:
            return finalize(alt.Chart(pd.DataFrame({"date": [], "value": []})).mark_point())

        plot_df = df.copy()
        plot_df["date"] = pd.to_datetime(plot_df["date"])
        value_column = "workout_count" if measure == WORKOUT_MEASURE_COUNT else "total_duration"
        plot_df["value"] = plot_df[value_column]
        y_title = "Workouts" if measure == WORKOUT_MEASURE_COUNT else "Minutes"
        date_title = date_tooltip_title(period)
        value_format = ",.0f"

        chart = (
            alt.Chart(plot_df)
            .mark_bar(cornerRadiusTopLeft=2, cornerRadiusTopRight=2)
            .encode(
                x=date_encoding(period),
                xOffset=alt.XOffset("activity:N"),
                y=numeric_axis(y_title, value_format=value_format, zero=True),
                color=alt.Color(
                    "activity:N",
                    title="Activity",
                    scale=alt.Scale(range=list(SERIES_COLORS)),
                ),
                tooltip=[
                    alt.Tooltip("date:T", title=date_title, format="%d %b %Y"),
                    alt.Tooltip("activity:N", title="Activity"),
                    alt.Tooltip("value:Q", title=y_title, format=value_format),
                ],
            )
        )
        return finalize(chart)
