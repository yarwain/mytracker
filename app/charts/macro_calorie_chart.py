"""Stacked macro calorie chart with logged calories and body mass subplot."""

import altair as alt
import pandas as pd

from app.charts.aggregation import Period
from app.charts.scales import tight_y_domain
from app.charts.theme import (
    BODY_MASS_COLOR,
    BODY_MASS_PANEL_HEIGHT,
    BODY_MASS_SHADOW,
    MACRO_COLORS,
    MACRO_PANEL_HEIGHT,
    date_encoding,
    date_tooltip_title,
    finalize,
    quantity_axis,
)
from app.config import BODY_MASS_AXIS_FLOOR_KG


class MacroCalorieChart:
    """Build stacked macro kcal bars with a body mass subplot below."""

    _COMPONENTS = (
        ("carb_kcal", "Carbs"),
        ("protein_kcal", "Protein"),
        ("fat_kcal", "Fat"),
    )

    def build(
        self,
        df: pd.DataFrame,
        *,
        period: Period = "weekly",
        body_mass_df: pd.DataFrame | None = None,
    ) -> alt.Chart:
        """Plot macro calories, logged calories, and optional body mass subplot."""
        if df.empty:
            return finalize(alt.Chart(pd.DataFrame({"date": [], "kcal": []})).mark_point())

        plot_df = df.copy()
        plot_df["date"] = pd.to_datetime(plot_df["date"])
        stacked = self._stacked_frame(plot_df)
        date_title = date_tooltip_title(period)
        x_enc = date_encoding(period)

        bars = (
            alt.Chart(stacked)
            .mark_bar(cornerRadiusTopLeft=2, cornerRadiusTopRight=2)
            .encode(
                x=x_enc,
                y=quantity_axis("kcal:Q", "Calories (kcal)", value_format=",.0f", zero=True),
                color=alt.Color(
                    "component:N",
                    title="Macros",
                    scale=alt.Scale(range=list(MACRO_COLORS)),
                ),
                tooltip=[
                    alt.Tooltip("date:T", title=date_title, format="%d %b %Y"),
                    alt.Tooltip("component:N", title="Macro"),
                    alt.Tooltip("kcal:Q", title="kcal", format=",.0f"),
                ],
            )
        )

        calories_line = (
            alt.Chart(plot_df)
            .mark_line(color="#546e7a", point=True, strokeWidth=2)
            .encode(
                x=x_enc,
                y=quantity_axis("calories:Q", "Calories (kcal)", value_format=",.0f", zero=True),
                tooltip=[
                    alt.Tooltip("date:T", title=date_title, format="%d %b %Y"),
                    alt.Tooltip("calories:Q", title="Logged kcal", format=",.0f"),
                ],
            )
        )

        kcal_chart = (
            alt.layer(bars, calories_line)
            .resolve_scale(y="shared", color="independent")
            .properties(height=MACRO_PANEL_HEIGHT)
        )

        if body_mass_df is None or body_mass_df.empty:
            return finalize(kcal_chart)

        body_mass_plot = self._align_body_mass_dates(plot_df, body_mass_df)
        if body_mass_plot.empty:
            return finalize(kcal_chart)

        unit = self._series_unit(body_mass_plot)
        axis_title = f"Body mass ({unit})"
        _, y_max = tight_y_domain(body_mass_plot["value"])
        body_mass_y = quantity_axis(
            "value:Q",
            axis_title,
            value_format=",.1f",
            domain=(BODY_MASS_AXIS_FLOOR_KG, y_max),
        )
        body_mass_tooltip = [
            alt.Tooltip("date:T", title=date_title, format="%d %b %Y"),
            alt.Tooltip("value:Q", title="Body mass", format=",.2f"),
            alt.Tooltip("unit:N", title="Unit"),
        ]
        top_x = date_encoding(period, hide_axis=True)
        bottom_x = date_encoding(period, title=date_title)

        kcal_chart = (
            alt.layer(
                bars.encode(x=top_x),
                calories_line.encode(x=top_x),
            )
            .resolve_scale(y="shared", color="independent")
            .properties(height=MACRO_PANEL_HEIGHT)
        )

        body_mass_shadow = (
            alt.Chart(body_mass_plot)
            .mark_line(strokeWidth=6, color=BODY_MASS_SHADOW, opacity=0.45)
            .encode(x=bottom_x, y=body_mass_y)
        )
        body_mass_line = (
            alt.Chart(body_mass_plot)
            .mark_line(point=True, strokeWidth=3, color=BODY_MASS_COLOR)
            .encode(x=bottom_x, y=body_mass_y, tooltip=body_mass_tooltip)
        )
        body_mass_chart = (
            alt.layer(body_mass_shadow, body_mass_line)
            .properties(height=BODY_MASS_PANEL_HEIGHT)
        )

        return finalize(
            alt.vconcat(kcal_chart, body_mass_chart).resolve_scale(x="shared"),
            height=None,
        )

    def _stacked_frame(self, plot_df: pd.DataFrame) -> pd.DataFrame:
        frames: list[pd.DataFrame] = []
        for column, label in self._COMPONENTS:
            part = plot_df[["date", column]].copy()
            part = part.rename(columns={column: "kcal"})
            part["component"] = label
            frames.append(part)
        return pd.concat(frames, ignore_index=True)

    @staticmethod
    def _align_body_mass_dates(
        macro_df: pd.DataFrame,
        body_mass_df: pd.DataFrame,
    ) -> pd.DataFrame:
        """Keep body mass points on the same dates as the macro chart."""
        body_mass_plot = body_mass_df.copy()
        body_mass_plot["date"] = pd.to_datetime(body_mass_plot["date"])
        macro_dates = pd.to_datetime(macro_df["date"]).drop_duplicates()
        return body_mass_plot[body_mass_plot["date"].isin(macro_dates)].sort_values("date")

    @staticmethod
    def _series_unit(df: pd.DataFrame) -> str:
        if "unit" not in df.columns:
            return "kg"
        unit = df["unit"].dropna()
        if unit.empty:
            return "kg"
        return str(unit.iloc[0])
