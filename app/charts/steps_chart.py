"""Altair chart for daily step totals on a real y-axis."""

import altair as alt
import pandas as pd

from app.charts.aggregation import Period


class StepsChart:
    """Build a line chart of step counts."""

    def __init__(self, *, height: int = 420) -> None:
        self._height = height

    def build(self, df: pd.DataFrame, *, period: Period = "weekly") -> alt.Chart:
        """Plot step totals without normalizing the y-axis."""
        if df.empty:
            return alt.Chart(pd.DataFrame({"date": [], "value": []})).mark_point()

        plot_df = df.copy()
        plot_df["date"] = pd.to_datetime(plot_df["date"])
        date_title = "Month" if period == "monthly" else "Date"

        return (
            alt.Chart(plot_df)
            .mark_line(point=True, strokeWidth=2)
            .encode(
                x=alt.X("date:T", title=date_title),
                y=alt.Y("value:Q", title="Steps", scale=alt.Scale(zero=False)),
                tooltip=[
                    alt.Tooltip("date:T", title=date_title),
                    alt.Tooltip("value:Q", title="Steps", format=",.0f"),
                ],
            )
            .properties(height=self._height)
        )
