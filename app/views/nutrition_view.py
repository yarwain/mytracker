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
from app.views.chart_layout import chart_panel, filter_toolbar, render_chart


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
        breakdown_df = self._repository.load_macro_calorie_breakdown()
        probe_df = breakdown_df if not breakdown_df.empty else pd.DataFrame({"date": []})
        year_options = available_years(probe_df) if not probe_df.empty else []

        filter_toolbar()
        self._render_filters(sources, available_metrics, year_options=year_options)

        selected_sources = self._selected_sources(sources)
        selected_metrics = self._selected_metrics(available_metrics)
        selected_years = self._selected_years(year_options)
        period = self._selected_period()

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
            st.warning("No data for the selected metrics and sources.")
            return

        if not year_options:
            year_options = available_years(df if not df.empty else breakdown_df)
            selected_years = self._selected_years(year_options)

        plot_df = pd.DataFrame()
        if not df.empty:
            plot_df = apply_period(filter_by_years(df, selected_years), period)

        macro_plot_df = resample_breakdown(
            filter_by_years(breakdown_df, selected_years),
            period,
        )
        body_mass_plot_df = self._load_body_mass_plot(selected_years, period)

        if plot_df.empty and macro_plot_df.empty:
            st.warning("No data for the selected years.")
            return

        period_label = "Monthly" if period == "monthly" else "Weekly"

        if not macro_plot_df.empty:
            macro_subtitle = (
                f"{period_label} macro calories from meal logs. "
                f"Days below {MIN_DAILY_CALORIES:.0f} kcal are excluded."
            )
            if not body_mass_plot_df.empty:
                macro_subtitle += " Body mass is shown in the subplot below."
            with chart_panel("Calories and macros", subtitle=macro_subtitle):
                render_chart(
                    self._macro_chart_builder.build(
                        macro_plot_df,
                        period=period,
                        body_mass_df=body_mass_plot_df,
                    )
                )

        if not plot_df.empty:
            trends_subtitle = (
                f"{period_label} averages per logged day. "
                f"Calories exclude days below {MIN_DAILY_CALORIES:.0f} kcal."
            )
            with chart_panel("Nutrition trends", subtitle=trends_subtitle):
                self._render_summary(plot_df, selected_metrics)
                render_chart(self._chart_builder.build(plot_df, selected_metrics, period=period))

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
        """Render compact nutrition controls above the charts."""
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
                    key="nutrition_source_filter",
                )
            with metric_col:
                st.multiselect(
                    "Trend metrics",
                    options=labels,
                    default=active_labels or default,
                    key="nutrition_metric_filter",
                )
        else:
            st.multiselect(
                "Trend metrics",
                options=labels,
                default=active_labels or default,
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
                else f"{latest['value']:.1f} {metric.unit}"
            )
            columns[index % len(columns)].metric(metric.label, value_text)

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
