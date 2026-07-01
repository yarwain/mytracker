"""Streamlit view for manually entered body measurements."""

from datetime import date

import pandas as pd
import streamlit as st

from app.charts.metric_trend_chart import MetricTrendChart
from app.config import USER_HEIGHT_CM, ManualMetric
from app.repositories.manual_metrics_repository import ManualMetricsRepository


class ManualMetricsView:
    """Render forms and charts for neck, waist, and hip measurements."""

    def __init__(self, repository: ManualMetricsRepository | None = None) -> None:
        self._repository = repository or ManualMetricsRepository()
        self._chart_builder = MetricTrendChart()

    def render(self) -> None:
        """Draw the manual measurements section."""
        st.subheader("Body measurements")
        st.caption(
            "Manually tracked neck, waist, and hip size in centimetres. "
            f"Body fat is calculated automatically with the US Army formula "
            f"(height fixed at {USER_HEIGHT_CM:.0f} cm)."
        )

        self._render_entry_form()

        metrics = self._repository.list_chart_metrics()
        selected_metrics = self._render_metric_filter(metrics)
        if not selected_metrics:
            st.info("Select at least one measurement to display.")
            return

        df = self._repository.load_metrics(selected_metrics)
        if df.empty:
            st.warning("No manual measurements saved yet.")
            return

        available_years = self._available_years(df)
        selected_years = self._render_year_filter(available_years, key="manual_years")
        filtered_df = self._filter_by_years(df, selected_years)

        if filtered_df.empty:
            st.warning("No data for the selected years.")
            return

        self._render_summary(filtered_df, selected_metrics)
        self._render_chart(filtered_df, selected_metrics)
        self._render_raw_data(filtered_df)

    def _render_entry_form(self) -> None:
        """Render a form for entering measurements."""
        metrics = self._repository.list_enterable_metrics()
        with st.form("manual_measurements_form", clear_on_submit=True):
            measured_date = st.date_input("Date", value=date.today())
            columns = st.columns(len(metrics))
            values: dict[str, float] = {}

            for column, metric in zip(columns, metrics, strict=True):
                entered = column.number_input(
                    f"{metric.label} ({metric.unit})",
                    min_value=0.0,
                    step=0.1,
                    format="%.1f",
                    key=f"manual_input_{metric.key}",
                )
                if entered > 0:
                    values[metric.key] = entered

            notes = st.text_input("Notes (optional)")
            submitted = st.form_submit_button("Save measurements")

        if submitted:
            if not values:
                st.error("Enter at least one measurement greater than zero.")
                return

            try:
                saved, body_fat = self._repository.upsert_measurements(
                    measured_date,
                    values,
                    notes=notes or None,
                )
            except Exception as exc:
                st.error(f"Could not save measurements: {exc}")
                return

            message = f"Saved {saved} measurement(s) for {measured_date.isoformat()}."
            if body_fat is not None:
                message += f" Body fat updated to {body_fat:.1f}%."
            st.success(message)
            st.rerun()

    def _render_metric_filter(self, metrics: list[ManualMetric]) -> list[ManualMetric]:
        """Render a multiselect for choosing visible measurements."""
        labels = [metric.label for metric in metrics]
        selected_labels = st.multiselect(
            "Measurements",
            options=labels,
            default=labels,
            help="Choose which manual measurements to show on the chart.",
            key="manual_metric_filter",
        )
        if not selected_labels:
            return []

        selected = {label for label in selected_labels}
        return [metric for metric in metrics if metric.label in selected]

    def _available_years(self, df: pd.DataFrame) -> list[int]:
        """Return sorted years present in the dataset."""
        dates = pd.to_datetime(df["date"])
        return sorted(dates.dt.year.unique().tolist())

    def _render_year_filter(self, available_years: list[int], *, key: str) -> list[int]:
        """Render a multiselect for choosing which years to display."""
        selected = st.multiselect(
            "Years",
            options=available_years,
            default=available_years,
            help="Show measurements for the selected years only.",
            key=key,
        )
        return selected or available_years

    def _filter_by_years(self, df: pd.DataFrame, years: list[int]) -> pd.DataFrame:
        """Return rows whose date falls within the selected years."""
        dates = pd.to_datetime(df["date"])
        mask = dates.dt.year.isin(years)
        return df.loc[mask].copy()

    def _render_summary(self, df: pd.DataFrame, metrics: list[ManualMetric]) -> None:
        """Show the latest value for each selected measurement."""
        columns = st.columns(min(len(metrics), 3))
        for index, metric in enumerate(metrics):
            metric_df = df[df["label"] == metric.label]
            if metric_df.empty:
                continue
            latest = metric_df.iloc[-1]
            columns[index % len(columns)].metric(
                metric.label,
                f"{latest['value']:.1f} {latest['unit']}",
            )

    def _render_chart(self, df: pd.DataFrame, metrics: list[ManualMetric]) -> None:
        """Plot selected measurements with independent y-scales."""
        chart = self._chart_builder.build(df, metrics)
        st.altair_chart(chart, use_container_width=True)

    def _render_raw_data(self, df: pd.DataFrame) -> None:
        """Show saved measurements."""
        with st.expander("Raw data"):
            st.dataframe(
                df.sort_values(["label", "date"]),
                use_container_width=True,
            )
