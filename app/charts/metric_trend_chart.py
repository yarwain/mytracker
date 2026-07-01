"""Altair charts for health metrics."""

from typing import Protocol

import altair as alt
import pandas as pd

from app.charts.scales import tight_y_domain


class ChartMetric(Protocol):
    """Metric definition required for trend charts."""

    label: str


class MetricTrendChart:
    """Build line charts with tight independent y-scales per metric."""

    def __init__(self, *, padding_ratio: float = 0.08, row_height: int = 180) -> None:
        self._padding_ratio = padding_ratio
        self._row_height = row_height

    def build(self, df: pd.DataFrame, metrics: list[ChartMetric]) -> alt.Chart:
        """Create stacked charts for the selected metrics.

        Each metric gets its own panel and y-axis range based on its min/max values.
        """
        charts: list[alt.Chart] = []
        for metric in metrics:
            subset = df[df["label"] == metric.label]
            if subset.empty:
                continue

            y_min, y_max = tight_y_domain(subset["value"], padding_ratio=self._padding_ratio)
            unit = subset["unit"].iloc[0]
            title = f"{metric.label} ({unit})"

            charts.append(
                alt.Chart(subset)
                .mark_line(point=True)
                .encode(
                    x=alt.X("date:T", title="Date"),
                    y=alt.Y(
                        "value:Q",
                        title=title,
                        scale=alt.Scale(domain=[y_min, y_max], zero=False),
                    ),
                    tooltip=[
                        alt.Tooltip("date:T", title="Week starting"),
                        alt.Tooltip("value:Q", title=title, format=".2f"),
                        alt.Tooltip("reading_count:Q", title="Readings"),
                    ],
                )
                .properties(title=title, height=self._row_height)
            )

        if not charts:
            return alt.Chart(pd.DataFrame({"date": [], "value": []})).mark_point()

        return alt.vconcat(*charts)
