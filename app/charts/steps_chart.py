"""Altair chart for daily step totals on a real y-axis."""

import altair as alt
import pandas as pd

from app.charts.aggregation import Period
from app.charts.theme import STEPS_COLOR, date_encoding, date_tooltip_title, finalize, numeric_axis


class StepsChart:
    """Build a compact line chart of step counts."""

    def build(self, df: pd.DataFrame, *, period: Period = "weekly") -> alt.Chart:
        """Plot step totals with a clear date axis and readable values."""
        if df.empty:
            return finalize(alt.Chart(pd.DataFrame({"date": [], "value": []})).mark_point())

        plot_df = df.copy()
        plot_df["date"] = pd.to_datetime(plot_df["date"])
        date_title = date_tooltip_title(period)
        x_enc = date_encoding(period)
        y_enc = numeric_axis("Steps", value_format=",.0f")
        tooltip = [
            alt.Tooltip("date:T", title=date_title, format="%d %b %Y"),
            alt.Tooltip("value:Q", title="Steps", format=",.0f"),
        ]

        area = (
            alt.Chart(plot_df)
            .mark_area(opacity=0.12, color=STEPS_COLOR)
            .encode(x=x_enc, y=y_enc)
        )
        line = (
            alt.Chart(plot_df)
            .mark_line(point=True, strokeWidth=2.2, color=STEPS_COLOR)
            .encode(x=x_enc, y=y_enc, tooltip=tooltip)
        )
        return finalize(alt.layer(area, line))
