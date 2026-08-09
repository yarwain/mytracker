"""Calories spent vs consumed chart with a diff subplot below."""

import altair as alt
import pandas as pd

from app.charts.aggregation import Period
from app.charts.theme import (
    BODY_MASS_PANEL_HEIGHT,
    MACRO_PANEL_HEIGHT,
    date_encoding,
    date_tooltip_title,
    finalize,
    quantity_axis,
)

SPENT_COLOR = "#ff7f0e"
CONSUMED_COLOR = "#2ca02c"
DIFF_COLOR = "#546e7a"
DIFF_SHADOW = "#b0bec5"


class EnergyBalanceChart:
    """Build spent/consumed lines with a bold diff line subplot below."""

    _SERIES_LABELS = {
        "spent_kcal": "Calories spent",
        "consumed_kcal": "Calories consumed",
    }

    def build(self, df: pd.DataFrame, *, period: Period = "weekly") -> alt.Chart:
        """Plot calories spent and consumed with a diff subplot."""
        if df.empty:
            return finalize(alt.Chart(pd.DataFrame({"date": [], "kcal": []})).mark_point())

        plot_df = df.copy()
        plot_df["date"] = pd.to_datetime(plot_df["date"])
        date_title = date_tooltip_title(period)
        x_enc = date_encoding(period)
        top_x = date_encoding(period, hide_axis=True)
        bottom_x = date_encoding(period, title=date_title)
        y_enc = quantity_axis("kcal:Q", "Calories (kcal)", value_format=",.0f", zero=True)

        lines_df = self._line_frame(plot_df)
        diff_df = plot_df.dropna(subset=["diff_kcal"]).copy()

        main_lines = (
            alt.Chart(lines_df)
            .mark_line(point=True, strokeWidth=2)
            .encode(
                x=x_enc,
                y=y_enc,
                color=alt.Color(
                    "series:N",
                    title="Series",
                    scale=alt.Scale(
                        domain=list(self._SERIES_LABELS.values()),
                        range=[SPENT_COLOR, CONSUMED_COLOR],
                    ),
                ),
                tooltip=[
                    alt.Tooltip("date:T", title=date_title, format="%d %b %Y"),
                    alt.Tooltip("series:N", title="Series"),
                    alt.Tooltip("kcal:Q", title="kcal", format=",.0f"),
                ],
            )
        )

        main_chart = (
            main_lines.encode(x=top_x)
            .properties(height=MACRO_PANEL_HEIGHT)
        )

        if diff_df.empty:
            return finalize(main_chart)

        diff_y = quantity_axis("diff_kcal:Q", "Consumed − spent (kcal)", value_format=",.0f", zero=True)
        diff_tooltip = [
            alt.Tooltip("date:T", title=date_title, format="%d %b %Y"),
            alt.Tooltip("diff_kcal:Q", title="Consumed − spent", format=",.0f"),
        ]

        diff_shadow = (
            alt.Chart(diff_df)
            .mark_line(strokeWidth=6, color=DIFF_SHADOW, opacity=0.45)
            .encode(x=bottom_x, y=diff_y)
        )
        diff_line = (
            alt.Chart(diff_df)
            .mark_line(point=True, strokeWidth=3, color=DIFF_COLOR)
            .encode(x=bottom_x, y=diff_y, tooltip=diff_tooltip)
        )
        diff_chart = alt.layer(diff_shadow, diff_line).properties(height=BODY_MASS_PANEL_HEIGHT)

        return finalize(
            alt.vconcat(main_chart, diff_chart).resolve_scale(x="shared"),
            height=None,
        )

    def _line_frame(self, plot_df: pd.DataFrame) -> pd.DataFrame:
        frames: list[pd.DataFrame] = []
        for column, label in self._SERIES_LABELS.items():
            part = plot_df[["date", column]].dropna(subset=[column]).copy()
            if part.empty:
                continue
            part = part.rename(columns={column: "kcal"})
            part["series"] = label
            frames.append(part)
        if not frames:
            return pd.DataFrame(columns=["date", "kcal", "series"])
        return pd.concat(frames, ignore_index=True)
