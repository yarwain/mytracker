"""Altair charts for health metrics."""

from typing import Protocol

import altair as alt
import pandas as pd

from app.charts.aggregation import Period
from app.charts.scales import tight_y_domain
from app.charts.theme import (
    BODY_MASS_COLOR,
    BODY_MASS_SHADOW,
    SERIES_COLORS,
    date_encoding,
    date_tooltip_title,
    finalize,
    numeric_axis,
)

HIGHLIGHT_METRIC_LABEL = "Body mass"


class ChartMetric(Protocol):
    """Metric definition required for trend charts."""

    label: str


class MetricTrendChart:
    """Build a combined line chart with an independent real y-axis per metric."""

    def __init__(self, *, padding_ratio: float = 0.08) -> None:
        self._padding_ratio = padding_ratio

    def build(
        self,
        df: pd.DataFrame,
        metrics: list[ChartMetric],
        *,
        period: Period = "weekly",
    ) -> alt.Chart:
        """Plot selected metrics on one chart with clear real-value axes."""
        selected_labels = {metric.label for metric in metrics}
        plot_df = self._prepare_plot_frame(df, selected_labels)
        if plot_df.empty:
            return finalize(alt.Chart(pd.DataFrame({"date": [], "value": []})).mark_point())

        date_title = date_tooltip_title(period)
        layers: list[alt.Chart] = []
        color_by_label = self._series_colors(plot_df["label"].unique().tolist())

        for index, (label, group) in enumerate(plot_df.groupby("label", sort=False)):
            y_min, y_max = tight_y_domain(group["value"], padding_ratio=self._padding_ratio)
            unit = self._series_unit(group)
            axis_title = f"{label} ({unit})" if unit else label
            orient = "left" if index % 2 == 0 else "right"
            color = color_by_label[label]
            tooltip = [
                alt.Tooltip("label:N", title="Metric"),
                alt.Tooltip("date:T", title=date_title, format="%d %b %Y"),
                alt.Tooltip("value:Q", title="Value", format=",.2f"),
                alt.Tooltip("unit:N", title="Unit"),
            ]
            x_enc = date_encoding(period, title=date_title if index == 0 else "")
            y_enc = numeric_axis(
                axis_title,
                value_format=",.2f",
                domain=(y_min, y_max),
                orient=orient,
            )

            if label == HIGHLIGHT_METRIC_LABEL:
                layers.append(
                    alt.Chart(group)
                    .mark_line(strokeWidth=6, color=BODY_MASS_SHADOW, opacity=0.45)
                    .encode(x=x_enc, y=y_enc)
                )
                layers.append(
                    alt.Chart(group)
                    .mark_line(point=True, strokeWidth=3, color=BODY_MASS_COLOR)
                    .encode(x=x_enc, y=y_enc, tooltip=tooltip)
                )
                continue

            layers.append(
                alt.Chart(group)
                .mark_line(point=True, strokeWidth=2.2, color=color)
                .encode(x=x_enc, y=y_enc, tooltip=tooltip)
            )

        if not layers:
            return finalize(alt.Chart(pd.DataFrame({"date": [], "value": []})).mark_point())

        return finalize(
            alt.layer(*layers).resolve_scale(y="independent", x="shared")
        )

    def _prepare_plot_frame(
        self,
        df: pd.DataFrame,
        selected_labels: set[str],
    ) -> pd.DataFrame:
        subset = df[df["label"].isin(selected_labels)].copy()
        if subset.empty:
            return subset

        plot_df = subset.copy()
        plot_df["date"] = pd.to_datetime(plot_df["date"])
        return plot_df.sort_values(["label", "date"])

    @staticmethod
    def _series_unit(group: pd.DataFrame) -> str:
        if "unit" not in group.columns:
            return ""
        unit = group["unit"].dropna()
        if unit.empty:
            return ""
        return str(unit.iloc[0])

    @staticmethod
    def _series_colors(labels: list[str]) -> dict[str, str]:
        colors: dict[str, str] = {}
        palette_index = 0
        for label in labels:
            if label == HIGHLIGHT_METRIC_LABEL:
                colors[label] = BODY_MASS_COLOR
                continue
            colors[label] = SERIES_COLORS[palette_index % len(SERIES_COLORS)]
            palette_index += 1
        return colors
