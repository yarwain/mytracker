"""Stacked macro calorie chart with logged calories and body mass overlay."""

import altair as alt
import pandas as pd

from app.charts.aggregation import Period
from app.charts.scales import tight_y_domain


class MacroCalorieChart:
    """Build stacked macro kcal bars with calorie and body mass overlays."""

    _COMPONENTS = (
        ("carb_kcal", "Carbs (4 kcal/g)"),
        ("protein_kcal", "Protein (4 kcal/g)"),
        ("fat_kcal", "Fat (9 kcal/g)"),
    )

    def __init__(self, *, height: int = 420) -> None:
        self._height = height

    def build(
        self,
        df: pd.DataFrame,
        *,
        period: Period = "weekly",
        body_mass_df: pd.DataFrame | None = None,
    ) -> alt.Chart:
        """Plot macro calories, logged calories, and optional body mass."""
        if df.empty:
            return alt.Chart(pd.DataFrame({"date": [], "kcal": []})).mark_point()

        plot_df = df.copy()
        plot_df["date"] = pd.to_datetime(plot_df["date"])
        stacked = self._stacked_frame(plot_df)
        date_title = "Month" if period == "monthly" else "Date"

        bars = (
            alt.Chart(stacked)
            .mark_bar()
            .encode(
                x=alt.X("date:T", title=date_title),
                y=alt.Y("kcal:Q", title="kcal", stack="zero"),
                color=alt.Color("component:N", title="Macro calories"),
                tooltip=[
                    alt.Tooltip("date:T", title=date_title),
                    alt.Tooltip("component:N", title="Component"),
                    alt.Tooltip("kcal:Q", title="kcal", format=".0f"),
                ],
            )
        )

        calories_line = (
            alt.Chart(plot_df)
            .mark_line(color="#1f1f1f", point=True, strokeWidth=2)
            .encode(
                x=alt.X("date:T", title=date_title),
                y=alt.Y("calories:Q", title="kcal"),
                tooltip=[
                    alt.Tooltip("date:T", title=date_title),
                    alt.Tooltip("calories:Q", title="Calories", format=".0f"),
                ],
            )
        )

        kcal_chart = alt.layer(bars, calories_line).resolve_scale(
            y="shared",
            color="independent",
        )

        if body_mass_df is None or body_mass_df.empty:
            return kcal_chart.properties(height=self._height)

        body_mass_plot = body_mass_df.copy()
        body_mass_plot["date"] = pd.to_datetime(body_mass_plot["date"])
        y_min, y_max = tight_y_domain(body_mass_plot["value"])
        unit = self._series_unit(body_mass_plot)
        axis_title = f"Body mass ({unit})" if unit else "Body mass"
        body_mass_tooltip = [
            alt.Tooltip("date:T", title=date_title),
            alt.Tooltip("value:Q", title="Body mass", format=".2f"),
            alt.Tooltip("unit:N", title="Unit"),
        ]
        x_enc = alt.X("date:T", title=date_title)
        y_enc = alt.Y(
            "value:Q",
            title=axis_title,
            scale=alt.Scale(domain=[y_min, y_max], clamp=True),
            axis=alt.Axis(orient="right"),
        )

        body_mass_shadow = (
            alt.Chart(body_mass_plot)
            .mark_line(strokeWidth=7, color="#9aa0a6", opacity=0.35)
            .encode(x=x_enc, y=y_enc)
        )
        body_mass_line = (
            alt.Chart(body_mass_plot)
            .mark_line(point=True, strokeWidth=3.5, color="#111111")
            .encode(x=x_enc, y=y_enc, tooltip=body_mass_tooltip)
        )

        return (
            alt.layer(kcal_chart, body_mass_shadow, body_mass_line)
            .resolve_scale(y="independent", color="independent")
            .properties(height=self._height)
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
    def _series_unit(df: pd.DataFrame) -> str:
        if "unit" not in df.columns:
            return "kg"
        unit = df["unit"].dropna()
        if unit.empty:
            return "kg"
        return str(unit.iloc[0])
