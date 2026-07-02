"""Streamlit view for weekly nutrition averages."""

import pandas as pd
import streamlit as st

from app.charts.aggregation import Period, resample_breakdown
from app.charts.macro_calorie_chart import MacroCalorieChart
from app.charts.metric_trend_chart import MetricTrendChart
from app.config import BODY_MASS_METRIC, MIN_DAILY_CALORIES, NutritionMetric
from app.repositories.nutrition_repository import NutritionRepository
from app.repositories.zepp_repository import ZeppRepository
from app.views.chart_controls import (
    apply_period,
    available_years,
    filter_by_years,
    render_period_filter,
    render_year_filter,
    render_year_period_row,
)


class NutritionView:
    """Render nutrition charts from Apple Health meal records."""

    _DEFAULT_METRICS = ("Carbohydrates", "Protein", "Total fat")

    def __init__(
        self,
        repository: NutritionRepository | None = None,
        zepp_repository: ZeppRepository | None = None,
    ) -> None:
        self._repository = repository or NutritionRepository()
        self._zepp_repository = zepp_repository or ZeppRepository()
        self._chart_builder = MetricTrendChart()
        self._macro_chart_builder = MacroCalorieChart()

    def render(self) -> None:
        """Draw the nutrition section."""
        available_metrics = self._repository.list_available_metrics()
        if not available_metrics:
            st.warning(
                "No nutrition data found in `apple_health_records`. Import Apple Health first."
            )
            return

        st.subheader("Nutrition")

        sources = self._repository.list_sources()
        selected_sources = self._selected_sources(sources)
        selected_metrics = self._selected_metrics(available_metrics)

        df = pd.DataFrame()
        if selected_metrics:
            df = self._repository.load_selected_metrics(
                selected_metrics,
                sources=selected_sources or None,
            )

        breakdown_df = self._repository.load_macro_calorie_breakdown(
            sources=selected_sources or None,
        )

        if df.empty and breakdown_df.empty:
            self._render_filters(sources, available_metrics, year_options=[])
            st.warning("No data for the selected metrics and sources.")
            return

        year_options = available_years(df if not df.empty else breakdown_df)
        selected_years = self._selected_years(year_options)
        period = self._selected_period()

        plot_df = pd.DataFrame()
        if not df.empty:
            plot_df = apply_period(filter_by_years(df, selected_years), period)

        macro_plot_df = resample_breakdown(
            filter_by_years(breakdown_df, selected_years),
            period,
        )
        body_mass_plot_df = self._load_body_mass_plot(selected_years, period)

        if plot_df.empty and macro_plot_df.empty:
            self._render_filters(sources, available_metrics, year_options=year_options)
            st.warning("No data for the selected years.")
            return

        if not macro_plot_df.empty:
            st.markdown("#### Macro calories vs logged calories")
            caption = (
                "Stacked bars show carbs×4, protein×4, and fat×9. "
                f"The black line shows logged calories from Apple Health. "
                f"Days below {MIN_DAILY_CALORIES:.0f} kcal are excluded."
            )
            if not body_mass_plot_df.empty:
                caption += (
                    " Body mass from Zepp Life morning readings uses a separate "
                    "right-hand scale and is drawn above the calories line."
                )
            st.caption(caption)
            self._render_macro_chart(
                macro_plot_df,
                period=period,
                body_mass_df=body_mass_plot_df,
            )

        if not plot_df.empty:
            period_label = "monthly" if period == "monthly" else "weekly"
            point_counts = plot_df.groupby("label", sort=False).size()
            st.markdown("#### Nutrition trends")
            st.caption(
                f"{period_label.capitalize()} averages per logged day on one combined chart. "
                f"Calories exclude days below {MIN_DAILY_CALORIES:.0f} kcal or with no intake. "
                "Each metric uses its own real y-axis scale. "
                + ", ".join(f"{label}: {count} points" for label, count in point_counts.items())
            )
            self._render_chart(plot_df, selected_metrics, period=period)
            self._render_summary(plot_df, selected_metrics)
            self._render_raw_data(plot_df)

        self._render_filters(sources, available_metrics, year_options=year_options)

    def _selected_sources(self, sources: list[str]) -> list[str]:
        if not sources:
            return []
        selected = st.session_state.get("nutrition_source_filter")
        if selected:
            return selected
        return sources

    def _selected_metrics(self, metrics: list[NutritionMetric]) -> list[NutritionMetric]:
        labels = [metric.label for metric in metrics]
        default = [label for label in self._DEFAULT_METRICS if label in labels]
        if not default:
            default = labels[:3] if len(labels) >= 3 else labels

        selected_labels = st.session_state.get("nutrition_metric_filter", default)
        if not selected_labels:
            return []

        selected = set(selected_labels)
        return [metric for metric in metrics if metric.label in selected]

    def _selected_years(self, year_options: list[int]) -> list[int]:
        selected = st.session_state.get("nutrition_years")
        if selected:
            return selected
        return year_options

    def _selected_period(self) -> Period:
        selected = st.session_state.get("nutrition_period", "Weekly")
        return "weekly" if selected == "Weekly" else "monthly"

    def _render_filters(
        self,
        sources: list[str],
        metrics: list[NutritionMetric],
        *,
        year_options: list[int],
    ) -> None:
        """Render compact nutrition chart controls below the plots."""
        st.markdown("##### Chart options")

        labels = [metric.label for metric in metrics]
        default = [label for label in self._DEFAULT_METRICS if label in labels]
        if not default:
            default = labels[:3] if len(labels) >= 3 else labels
        active_labels = [metric.label for metric in self._selected_metrics(metrics)]

        if sources:
            source_col, metric_col = st.columns(2)
            with source_col:
                st.multiselect(
                    "Sources",
                    options=sources,
                    default=self._selected_sources(sources),
                    help="Filter meal records by the app that wrote them to Apple Health.",
                    key="nutrition_source_filter",
                )
            with metric_col:
                st.multiselect(
                    "Metrics",
                    options=labels,
                    default=active_labels or default,
                    help="Choose which nutrition metrics to show on the trend chart.",
                    key="nutrition_metric_filter",
                )
        else:
            st.multiselect(
                "Metrics",
                options=labels,
                default=active_labels or default,
                help="Choose which nutrition metrics to show on the trend chart.",
                key="nutrition_metric_filter",
            )

        if year_options:
            render_year_period_row(
                year_options,
                year_key="nutrition_years",
                period_key="nutrition_period",
            )
        else:
            render_period_filter(key="nutrition_period")

    def _render_summary(self, df: pd.DataFrame, metrics: list[NutritionMetric]) -> None:
        """Show the latest value for each selected metric."""
        columns = st.columns(min(len(metrics), 4))
        for index, metric in enumerate(metrics):
            metric_df = df[df["label"] == metric.label]
            if metric_df.empty:
                continue
            latest = metric_df.iloc[-1]
            value_text = (
                f"{latest['value']:.0f} {latest['unit']}"
                if metric.unit in {"mg", "kcal"}
                else f"{latest['value']:.1f} {latest['unit']}"
            )
            columns[index % len(columns)].metric(metric.label, value_text)

    def _render_chart(
        self,
        df: pd.DataFrame,
        metrics: list[NutritionMetric],
        *,
        period: Period,
    ) -> None:
        """Plot selected nutrition metrics on one combined chart."""
        chart = self._chart_builder.build(df, metrics, period=period)
        st.altair_chart(chart, use_container_width=True)

    def _load_body_mass_plot(self, selected_years: list[int], period: Period) -> pd.DataFrame:
        """Load body mass aligned to the macro chart period and year filter."""
        available = self._zepp_repository.list_available_metrics()
        if BODY_MASS_METRIC not in available:
            return pd.DataFrame(columns=["date", "value", "unit", "label"])

        daily = self._zepp_repository.load_daily_metric(BODY_MASS_METRIC)
        if daily.empty:
            return pd.DataFrame(columns=["date", "value", "unit", "label"])

        daily = daily.copy()
        daily["label"] = BODY_MASS_METRIC.label
        return apply_period(filter_by_years(daily, selected_years), period)

    def _render_macro_chart(
        self,
        df: pd.DataFrame,
        *,
        period: Period,
        body_mass_df: pd.DataFrame | None = None,
    ) -> None:
        """Plot stacked macro calories with logged calories and body mass overlay."""
        chart = self._macro_chart_builder.build(
            df,
            period=period,
            body_mass_df=body_mass_df,
        )
        st.altair_chart(chart, use_container_width=True)

    def _render_raw_data(self, df: pd.DataFrame) -> None:
        """Show the underlying chart data."""
        with st.expander("Raw data"):
            st.dataframe(
                df.sort_values(["label", "date"]),
                use_container_width=True,
            )
