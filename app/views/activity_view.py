"""Streamlit view for steps and workouts."""

import pandas as pd
import streamlit as st

from app.charts.aggregation import Period, resample_workout_breakdown
from app.charts.steps_chart import StepsChart
from app.charts.workout_activity_chart import WorkoutActivityChart
from app.config import WORKOUT_MEASURE_COUNT, WORKOUT_MEASURE_DURATION
from app.repositories.activity_repository import ActivityRepository
from app.views.chart_controls import (
    apply_period,
    available_years,
    filter_by_years,
    render_period_filter,
    render_year_filter,
    render_year_period_row,
)
from app.views.chart_layout import chart_panel, filter_toolbar, render_chart


class ActivityView:
    """Render steps and workout charts with source priority and real scales."""

    def __init__(self, repository: ActivityRepository | None = None) -> None:
        self._repository = repository or ActivityRepository()
        self._steps_chart = StepsChart()
        self._workout_chart = WorkoutActivityChart()

    def render(self) -> None:
        """Draw the activity section."""
        st.subheader("Activity")

        if not self._repository.has_data():
            st.warning(
                "No activity data found. Import Apple Health with steps or workouts first."
            )
            return

        steps_df = self._repository.load_steps()
        workouts_df = self._repository.load_workout_breakdown()
        workout_activities = self._repository.list_workout_activities()

        combined = pd.concat(
            [frame for frame in (steps_df, workouts_df) if not frame.empty],
            ignore_index=True,
        )
        if combined.empty:
            st.warning("No activity data for the current selection.")
            return

        year_options = available_years(combined)
        filter_toolbar()
        self._render_filters(workout_activities, year_options=year_options)

        selected_activities = self._selected_workout_activities(workout_activities)
        workout_measure = self._selected_workout_measure()
        selected_years = self._selected_years(year_options)
        steps_period = self._selected_steps_period()
        workout_period = self._selected_workout_period()

        steps_plot = pd.DataFrame()
        if not steps_df.empty:
            steps_plot = apply_period(filter_by_years(steps_df, selected_years), steps_period)

        workouts_plot = pd.DataFrame()
        if not workouts_df.empty and selected_activities:
            filtered = workouts_df[workouts_df["activity"].isin(selected_activities)]
            workouts_plot = resample_workout_breakdown(
                filter_by_years(filtered, selected_years),
                workout_period,
            )

        if steps_plot.empty and workouts_plot.empty:
            st.warning("No data for the selected years.")
            return

        if not steps_plot.empty:
            steps_source = self._repository.describe_steps_sources(steps_df)
            steps_label = "Monthly" if steps_period == "monthly" else "Weekly"
            with chart_panel(
                "Steps",
                subtitle=(
                    f"{steps_label} average daily steps from {steps_source}. "
                    "Same-day conflicts prefer Polar, then Garmin."
                ),
            ):
                render_chart(self._steps_chart.build(steps_plot, period=steps_period))
                latest = steps_plot.iloc[-1]
                st.metric("Latest average", f"{latest['value']:,.0f} steps")

        if not workouts_plot.empty:
            workout_source = workouts_df.iloc[0]["source_name"]
            workout_label = "Monthly" if workout_period == "monthly" else "Weekly"
            measure_label = "count" if workout_measure == WORKOUT_MEASURE_COUNT else "minutes"
            with chart_panel(
                "Workouts",
                subtitle=(
                    f"{workout_label} workout {measure_label} by activity from {workout_source}."
                ),
            ):
                render_chart(
                    self._workout_chart.build(
                        workouts_plot,
                        period=workout_period,
                        measure=workout_measure,
                    )
                )

        with st.expander("Table data"):
            frames: list[pd.DataFrame] = []
            if not steps_plot.empty:
                frames.append(steps_plot.assign(series="Steps"))
            if not workouts_plot.empty:
                frames.append(workouts_plot.assign(series="Workouts"))
            if frames:
                st.dataframe(
                    pd.concat(frames, ignore_index=True).sort_values(["series", "date"]),
                    use_container_width=True,
                    hide_index=True,
                )

    def _selected_workout_activities(self, activities: list[str]) -> list[str]:
        if not activities:
            return []
        selected = st.session_state.get("activity_workout_activities")
        if selected:
            return [activity for activity in selected if activity in activities]
        return activities

    def _selected_workout_measure(self) -> str:
        selected = st.session_state.get("activity_workout_measure", "Count")
        return WORKOUT_MEASURE_COUNT if selected == "Count" else WORKOUT_MEASURE_DURATION

    def _selected_years(self, year_options: list[int]) -> list[int]:
        selected = st.session_state.get("activity_years")
        if selected:
            return selected
        return year_options

    def _selected_steps_period(self) -> Period:
        selected = st.session_state.get("activity_steps_period", "Weekly")
        return "weekly" if selected == "Weekly" else "monthly"

    def _selected_workout_period(self) -> Period:
        selected = st.session_state.get("activity_workout_period", "Weekly")
        return "weekly" if selected == "Weekly" else "monthly"

    def _render_filters(
        self,
        workout_activities: list[str],
        *,
        year_options: list[int],
    ) -> None:
        """Render compact activity controls above the charts."""
        if workout_activities:
            if year_options:
                year_col, steps_col, workout_col, measure_col = st.columns([2, 1, 1, 1])
                with year_col:
                    render_year_filter(year_options, key="activity_years")
                with steps_col:
                    render_period_filter(key="activity_steps_period", label="Steps")
                with workout_col:
                    render_period_filter(key="activity_workout_period", label="Workouts")
                with measure_col:
                    st.segmented_control(
                        "Show",
                        options=["Count", "Duration"],
                        default=st.session_state.get("activity_workout_measure", "Count"),
                        key="activity_workout_measure",
                    )
            else:
                steps_col, workout_col, measure_col = st.columns([1, 1, 1])
                with steps_col:
                    render_period_filter(key="activity_steps_period", label="Steps")
                with workout_col:
                    render_period_filter(key="activity_workout_period", label="Workouts")
                with measure_col:
                    st.segmented_control(
                        "Show",
                        options=["Count", "Duration"],
                        default=st.session_state.get("activity_workout_measure", "Count"),
                        key="activity_workout_measure",
                    )

            st.multiselect(
                "Activities",
                options=workout_activities,
                default=self._selected_workout_activities(workout_activities),
                key="activity_workout_activities",
            )
        elif year_options:
            year_col, steps_col = st.columns([2, 1])
            with year_col:
                render_year_filter(year_options, key="activity_years")
            with steps_col:
                render_period_filter(key="activity_steps_period", label="Steps")
