"""Streamlit view for Zepp Life metrics."""

import pandas as pd
import streamlit as st

from app.charts.metric_trend_chart import MetricTrendChart
from app.config import MORNING_WINDOW, HealthMetric
from app.repositories.zepp_repository import ZeppRepository


class ZeppMetricsView:
    """Render selectable Zepp metrics with independent chart scales."""

    def __init__(self, repository: ZeppRepository | None = None) -> None:
        self._repository = repository or ZeppRepository()
        self._chart_builder = MetricTrendChart()

    def render(self) -> None:
        """Draw the Zepp metrics section."""
        available_metrics = self._repository.list_available_metrics()
        if not available_metrics:
            st.warning("No Zepp Life metrics found in `apple_health_records`.")
            return

        st.subheader("Zepp Life")

        selected_metrics = self._render_metric_filter(available_metrics)
        if not selected_metrics:
            st.info("Select at least one metric to display.")
            return

        df = self._repository.load_selected_metrics(selected_metrics)
        if df.empty:
            st.warning("No data for the selected metrics.")
            return

        available_years = self._available_years(df)
        selected_years = self._render_year_filter(available_years)
        filtered_df = self._filter_by_years(df, selected_years)

        if filtered_df.empty:
            st.warning("No data for the selected years.")
            return

        weekly_points = filtered_df.groupby("label", sort=False).size()
        st.caption(
            "Weekly averages from Zepp Life morning readings "
            f"({MORNING_WINDOW.label()}). "
            + ", ".join(f"{label}: {count} weeks" for label, count in weekly_points.items())
            + ". Each date is the Monday starting that week."
        )

        self._render_summary(filtered_df, selected_metrics)
        self._render_chart(filtered_df, selected_metrics)
        self._render_raw_data(filtered_df)

    def _render_metric_filter(self, metrics: list[HealthMetric]) -> list[HealthMetric]:
        """Render a multiselect for choosing visible metrics."""
        labels = [metric.label for metric in metrics]
        default = [metric.label for metric in metrics if metric.label == "Body mass"]
        if not default:
            default = labels[:1]

        selected_labels = st.multiselect(
            "Metrics",
            options=labels,
            default=default,
            help="Choose which Zepp metrics to show on the chart.",
        )
        if not selected_labels:
            return []

        label_set = set(selected_labels)
        return [metric for metric in metrics if metric.label in label_set]

    def _available_years(self, df: pd.DataFrame) -> list[int]:
        """Return sorted years present in the dataset."""
        dates = pd.to_datetime(df["date"])
        return sorted(dates.dt.year.unique().tolist())

    def _render_year_filter(self, available_years: list[int]) -> list[int]:
        """Render a multiselect for choosing which years to display."""
        selected = st.multiselect(
            "Years",
            options=available_years,
            default=available_years,
            help="Show metrics for the selected years only.",
        )
        return selected or available_years

    def _filter_by_years(self, df: pd.DataFrame, years: list[int]) -> pd.DataFrame:
        """Return rows whose date falls within the selected years."""
        dates = pd.to_datetime(df["date"])
        mask = dates.dt.year.isin(years)
        return df.loc[mask].copy()

    def _render_summary(self, df: pd.DataFrame, metrics: list[HealthMetric]) -> None:
        """Show the latest value for each selected metric."""
        columns = st.columns(min(len(metrics), 4))
        for index, metric in enumerate(metrics):
            metric_df = df[df["label"] == metric.label]
            if metric_df.empty:
                continue
            latest = metric_df.iloc[-1]
            columns[index % len(columns)].metric(
                metric.label,
                f"{latest['value']:.1f} {latest['unit']}",
            )

    def _render_chart(self, df: pd.DataFrame, metrics: list[HealthMetric]) -> None:
        """Plot selected metrics with independent y-scales."""
        chart = self._chart_builder.build(df, metrics)
        st.altair_chart(chart, use_container_width=True)

    def _render_raw_data(self, df: pd.DataFrame) -> None:
        """Show the underlying weekly aggregates."""
        with st.expander("Raw data"):
            st.dataframe(
                df.sort_values(["label", "date"]),
                use_container_width=True,
            )
