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
        st.caption(
            "Manual neck, waist, and hip tracking in centimetres with US Army body fat "
            f"(height fixed at {USER_HEIGHT_CM:.0f} cm), combined with Zepp Life morning "
            f"readings ({MORNING_WINDOW.label()})."
        )

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

        period_label = "monthly" if period == "monthly" else "weekly"
        point_counts = plot_df.groupby("label", sort=False).size()
        st.caption(
            f"{period_label.capitalize()} averages on one combined chart. "
            "Each metric uses its own real y-axis scale. "
            + ", ".join(f"{label}: {count} points" for label, count in point_counts.items())
        )

        chart_metrics = [
            metric
            for metric in manual_metrics + zepp_metrics
            if metric.label in selected_labels
        ]
        self._render_summary(plot_df, chart_metrics)
        self._render_chart(plot_df, chart_metrics, period=period)
        self._render_raw_data(plot_df)

    def _render_entry_form(self) -> None:
        """Render a compact single-row form for entering manual measurements."""
        with st.form("manual_measurements_form", clear_on_submit=True):
            date_col, neck_col, waist_col, hip_col, save_col = st.columns([1.4, 1, 1, 1, 0.7])
            values: dict[str, float] = {}

            with date_col:
                measured_date = st.date_input("Date", value=date.today())
            with neck_col:
                neck = st.number_input(
                    "Neck (cm)",
                    min_value=0.0,
                    step=0.1,
                    format="%.1f",
                    key="manual_input_neck",
                )
                if neck > 0:
                    values["neck"] = neck
            with waist_col:
                waist = st.number_input(
                    "Waist (cm)",
                    min_value=0.0,
                    step=0.1,
                    format="%.1f",
                    key="manual_input_waist",
                )
                if waist > 0:
                    values["waist"] = waist
            with hip_col:
                hip = st.number_input(
                    "Hips (cm)",
                    min_value=0.0,
                    step=0.1,
                    format="%.1f",
                    key="manual_input_hip",
                )
                if hip > 0:
                    values["hip"] = hip
            with save_col:
                st.write("")
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

    def _render_metric_filter(self, labels: list[str]) -> list[str]:
        """Render a multiselect for choosing visible measurements."""
        default = [label for label in self._DEFAULT_LABELS if label in labels]
        if not default:
            default = [label for label in labels if label != "Neck size"] or labels[:1]

        selected_labels = st.multiselect(
            "Measurements",
            options=labels,
            default=default,
            help="Choose manual and Zepp Life measurements to show on the chart.",
            key="body_metric_filter",
        )
        return selected_labels

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
            columns[index % len(columns)].metric(metric.label, value_text)

    def _render_chart(
        self,
        df: pd.DataFrame,
        metrics: list[ManualMetric | HealthMetric],
        *,
        period: Period,
    ) -> None:
        """Plot selected measurements on one combined chart."""
        chart = self._chart_builder.build(df, metrics, period=period)
        st.altair_chart(chart, use_container_width=True)

    def _render_raw_data(self, df: pd.DataFrame) -> None:
        """Show saved measurements."""
        with st.expander("Raw data"):
            st.dataframe(
                df.sort_values(["label", "date"]),
                use_container_width=True,
            )
