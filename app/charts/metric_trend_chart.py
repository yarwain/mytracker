"""Altair charts for health metrics."""

from typing import Protocol

import altair as alt
import pandas as pd

from app.charts.aggregation import Period
from app.charts.scales import tight_y_domain

HIGHLIGHT_METRIC_LABEL = "Body mass"
SERIES_COLORS = (
    "#4c78a8",
    "#f58518",
    "#e45756",
    "#72b7b2",
    "#54a24b",
    "#b279a2",
    "#ff9da6",
    "#9d755d",
)


class ChartMetric(Protocol):
    """Metric definition required for trend charts."""

    label: str


class MetricTrendChart:
    """Build a combined line chart with an independent real y-axis per metric."""

    def __init__(self, *, padding_ratio: float = 0.08, height: int = 480) -> None:
        self._padding_ratio = padding_ratio
        self._height = height

    def build(
        self,
        df: pd.DataFrame,
        metrics: list[ChartMetric],
        *,
        period: Period = "weekly",
    ) -> alt.Chart:
        """Plot selected metrics on one chart with real, per-line y scales."""
        selected_labels = {metric.label for metric in metrics}
        plot_df = self._prepare_plot_frame(df, selected_labels)
        if plot_df.empty:
            return alt.Chart(pd.DataFrame({"date": [], "value": []})).mark_point()

        date_title = "Month" if period == "monthly" else "Date"
        layers: list[alt.Chart] = []
        color_by_label = self._series_colors(plot_df["label"].unique().tolist())

        for index, (label, group) in enumerate(plot_df.groupby("label", sort=False)):
            y_min, y_max = tight_y_domain(group["value"], padding_ratio=self._padding_ratio)
            unit = self._series_unit(group)
            axis_title = f"{label} ({unit})" if unit else label
            tooltip = [
                alt.Tooltip("label:N", title="Metric"),
                alt.Tooltip("date:T", title=date_title),
                alt.Tooltip("value:Q", title="Value", format=".2f"),
                alt.Tooltip("unit:N", title="Unit"),
            ]
            x_enc = alt.X("date:T", title=date_title if index == 0 else "")
            y_enc = alt.Y(
                "value:Q",
                title=axis_title,
                scale=alt.Scale(domain=[y_min, y_max], clamp=True),
            )

            if label == HIGHLIGHT_METRIC_LABEL:
                layers.append(
                    alt.Chart(group)
                    .mark_line(strokeWidth=7, color="#9aa0a6", opacity=0.35)
                    .encode(x=x_enc, y=y_enc)
                )
                layers.append(
                    alt.Chart(group)
                    .mark_line(point=True, strokeWidth=3.5, color="#111111")
                    .encode(x=x_enc, y=y_enc, tooltip=tooltip)
                )
                continue

            layers.append(
                alt.Chart(group)
                .mark_line(point=True, strokeWidth=1.5, color=color_by_label[label])
                .encode(x=x_enc, y=y_enc, tooltip=tooltip)
            )

        if not layers:
            return alt.Chart(pd.DataFrame({"date": [], "value": []})).mark_point()

        return (
            alt.layer(*layers)
            .resolve_scale(y="independent", x="shared")
            .properties(height=self._height)
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
        return {
            label: SERIES_COLORS[index % len(SERIES_COLORS)]
            for index, label in enumerate(labels)
        }
