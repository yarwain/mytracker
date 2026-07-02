"""Shared Altair styling for dashboard charts."""

import altair as alt

from app.charts.aggregation import Period

CHART_HEIGHT = 260
FACET_ROW_HEIGHT = 78
MACRO_PANEL_HEIGHT = 180
BODY_MASS_PANEL_HEIGHT = 100
BODY_MASS_COLOR = "#d81b60"
BODY_MASS_SHADOW = "#f48fb1"

SERIES_COLORS = (
    "#1f77b4",
    "#ff7f0e",
    "#2ca02c",
    "#9467bd",
    "#17becf",
    "#e377c2",
    "#bcbd22",
    "#8c564b",
)

MACRO_COLORS = ("#42a5f5", "#66bb6a", "#ffa726")
STEPS_COLOR = "#1f77b4"


def date_axis(period: Period) -> alt.Axis:
    """Return a readable temporal axis for weekly or monthly charts."""
    if period == "monthly":
        return alt.Axis(
            format="%b %Y",
            labelAngle=-30,
            labelOverlap=False,
            tickCount=8,
            grid=False,
        )
    return alt.Axis(
        format="%d %b",
        labelAngle=-30,
        labelOverlap=False,
        tickCount=12,
        grid=True,
    )


def date_encoding(
    period: Period,
    *,
    title: str | None = None,
    hide_axis: bool = False,
) -> alt.X:
    """Encode chart dates with a clear axis title and tick format."""
    axis_title = title or ("Month" if period == "monthly" else "Week")
    scale = alt.Scale(nice=False)
    if period == "weekly":
        scale = alt.Scale(nice=False, padding=20)
    axis = alt.Axis(labels=False, ticks=False, title=None) if hide_axis else date_axis(period)
    display_title = None if hide_axis else axis_title
    return alt.X("date:T", title=display_title, axis=axis, scale=scale)


def date_tooltip_title(period: Period) -> str:
    """Return a tooltip label for chart dates."""
    return "Month" if period == "monthly" else "Week starting"


def numeric_axis(
    title: str,
    *,
    orient: str = "left",
    value_format: str = ",.0f",
    domain: tuple[float, float] | None = None,
    zero: bool = False,
) -> alt.Y:
    """Encode numeric values with a readable y-axis."""
    scale_kwargs: dict = {"zero": zero}
    if domain is not None:
        scale_kwargs = {"domain": list(domain), "clamp": True, "zero": zero}
    return alt.Y(
        "value:Q",
        title=title,
        axis=alt.Axis(format=value_format, orient=orient, grid=True),
        scale=alt.Scale(**scale_kwargs),
    )


def quantity_axis(
    field: str,
    title: str,
    *,
    orient: str = "left",
    value_format: str = ",.0f",
    zero: bool = False,
    domain: tuple[float, float] | None = None,
) -> alt.Y:
    """Encode an arbitrary numeric field with a readable y-axis."""
    scale_kwargs: dict = {"zero": zero}
    if domain is not None:
        scale_kwargs = {"domain": list(domain), "clamp": True, "zero": zero}
    return alt.Y(
        field,
        title=title,
        axis=alt.Axis(format=value_format, orient=orient, grid=True),
        scale=alt.Scale(**scale_kwargs),
    )


def finalize(chart: alt.TopLevelSpec, *, height: int | None = CHART_HEIGHT) -> alt.TopLevelSpec:
    """Apply shared visual polish to a chart."""
    styled = (
        chart.configure_view(strokeWidth=0, fill="#ffffff")
        .configure_axis(
            labelFontSize=11,
            titleFontSize=12,
            gridColor="#e8edf2",
            domainColor="#b0bec5",
            labelColor="#37474f",
            titleColor="#263238",
            titlePadding=8,
            labelPadding=4,
        )
        .configure_legend(
            labelFontSize=11,
            titleFontSize=11,
            orient="top",
            direction="horizontal",
            titleAnchor="middle",
            labelLimit=180,
        )
    )
    if height is None:
        return styled
    return styled.properties(height=height)
