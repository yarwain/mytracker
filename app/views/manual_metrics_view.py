"""Streamlit view for manual and Zepp body measurements."""

from datetime import date

import pandas as pd
import streamlit as st

from app.charts.aggregation import Period
from app.charts.metric_trend_chart import MetricTrendChart
from app.config import MORNING_WINDOW, USER_HEIGHT_CM, HealthMetric, ManualMetric
from app.repositories.manual_metrics_repository import ManualMetricsRepository
from app.repositories.zepp_repository import ZeppRepository
from app.views.chart_controls import (
    apply_period,
    available_years,
    filter_by_years,
    render_period_filter,
    render_year_filter,
)
from app.views.chart_layout import chart_panel, filter_toolbar, render_chart


class ManualMetricsView:
    """Render manual entry, Zepp Life, and combined body measurement charts."""

    _DEFAULT_LABELS = (
        "Waist size",
        "Hip size",
        "Body fat (US Army)",
        "Body mass",
    )

    def __init__(
        self,
        manual_repository: ManualMetricsRepository | None = None,
        zepp_repository: ZeppRepository | None = None,
    ) -> None:
        self._manual_repository = manual_repository or ManualMetricsRepository()
        self._zepp_repository = zepp_repository or ZeppRepository()
        self._chart_builder = MetricTrendChart()

    def render(self) -> None:
        """Draw the combined body measurements section."""
        st.subheader("Body measurements")

        self._render_entry_form()

        manual_metrics = self._manual_repository.list_chart_metrics()
        zepp_metrics = self._zepp_repository.list_available_metrics()
        all_labels = [metric.label for metric in manual_metrics] + [
            metric.label for metric in zepp_metrics
        ]
        if not all_labels:
            st.warning("No body measurement data found.")
            return

        preload_frames: list[pd.DataFrame] = []
        if manual_metrics:
            manual_df = self._manual_repository.load_metrics(manual_metrics)
            if not manual_df.empty:
                preload_frames.append(manual_df)
        if zepp_metrics:
            zepp_df = self._zepp_repository.load_selected_metrics(zepp_metrics)
            if not zepp_df.empty:
                preload_frames.append(zepp_df)
        if not preload_frames:
            st.warning("No body measurement data found.")
            return

        df_all = pd.concat(preload_frames, ignore_index=True)
        filter_toolbar()
        filter_col, year_col, period_col = st.columns([3, 2, 1])
        with filter_col:
            selected_labels = self._render_metric_filter(all_labels)
        with year_col:
            selected_years = render_year_filter(available_years(df_all), key="body_years")
        with period_col:
            period = render_period_filter(key="body_period")

        if not selected_labels:
            st.info("Select at least one measurement to display.")
            return

        df = df_all[df_all["label"].isin(selected_labels)]
        plot_df = apply_period(filter_by_years(df, selected_years), period)

        if plot_df.empty:
            st.warning("No data for the selected years.")
            return

        chart_metrics = [
            metric
            for metric in manual_metrics + zepp_metrics
            if metric.label in selected_labels
        ]
        period_label = "Monthly" if period == "monthly" else "Weekly"
        subtitle = (
            f"{period_label} averages. Manual cm entries and Zepp morning readings "
            f"({MORNING_WINDOW.label()}). US Army body fat uses {USER_HEIGHT_CM:.0f} cm height."
        )

        with chart_panel("Body measurement trends", subtitle=subtitle):
            self._render_summary(plot_df, chart_metrics)
            self._render_chart(plot_df, chart_metrics, period=period)

    def _render_entry_form(self) -> None:
        """Render a compact form for entering manual measurements."""
        enterable = self._manual_repository.list_enterable_metrics()
        row_size = 4

        with st.form("manual_measurements_form", clear_on_submit=True):
            values: dict[str, float] = {}
            first_row = enterable[:row_size]
            second_row = enterable[row_size:]

            cols = st.columns([1.4] + [1] * len(first_row))
            with cols[0]:
                measured_date = st.date_input("Date", value=date.today())
            for column, metric in zip(cols[1:], first_row, strict=True):
                with column:
                    self._collect_metric_input(metric, values)

            if second_row:
                bottom_cols = st.columns([1] * (len(second_row) + 1))
                for column, metric in zip(bottom_cols[:-1], second_row, strict=True):
                    with column:
                        self._collect_metric_input(metric, values)
                with bottom_cols[-1]:
                    st.write("")
                    submitted = st.form_submit_button("Save", use_container_width=True)
            else:
                submitted = st.form_submit_button("Save", use_container_width=True)

        if submitted:
            if not values:
                st.error("Enter at least one measurement greater than zero.")
                return

            try:
                saved, body_fat = self._manual_repository.upsert_measurements(
                    measured_date,
                    values,
                )
            except Exception as exc:
                st.error(f"Could not save measurements: {exc}")
                return

            message = f"Saved {saved} measurement(s) for {measured_date.isoformat()}."
            if body_fat is not None:
                message += f" Body fat updated to {body_fat:.1f}%."
            st.success(message)
            st.rerun()

    def _collect_metric_input(self, metric: ManualMetric, values: dict[str, float]) -> None:
        """Read one measurement input and store it when greater than zero."""
        label = metric.label.replace(" size", "")
        if metric.unit == "kg":
            label = "Weight"
        value = st.number_input(
            f"{label} ({metric.unit})",
            min_value=0.0,
            step=0.1,
            format="%.1f",
            key=f"manual_input_{metric.key}",
        )
        if value > 0:
            values[metric.key] = value

    def _render_metric_filter(self, labels: list[str]) -> list[str]:
        """Render a multiselect for choosing visible measurements."""
        default = [label for label in self._DEFAULT_LABELS if label in labels]
        if not default:
            default = [label for label in labels if label != "Neck size"] or labels[:1]

        return st.multiselect(
            "Measurements",
            options=labels,
            default=default,
            key="body_metric_filter",
        )

    def _render_summary(
        self,
        df: pd.DataFrame,
        metrics: list[ManualMetric | HealthMetric],
    ) -> None:
        """Show the latest value for each selected measurement."""
        columns = st.columns(min(len(metrics), 4))
        for index, metric in enumerate(metrics):
            metric_df = df[df["label"] == metric.label]
            if metric_df.empty:
                continue
            latest = metric_df.iloc[-1]
            unit = latest["unit"]
            value_text = (
                f"{latest['value']:.1f} {unit}"
                if unit != "mg"
                else f"{latest['value']:.0f} {unit}"
            )
            columns[index % len(columns)].metric(metric.label, value_text, label_visibility="visible")

    def _render_chart(
        self,
        df: pd.DataFrame,
        metrics: list[ManualMetric | HealthMetric],
        *,
        period: Period,
    ) -> None:
        """Plot selected measurements on one combined chart."""
        render_chart(self._chart_builder.build(df, metrics, period=period))
