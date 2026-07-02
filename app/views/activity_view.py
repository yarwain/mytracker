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
        selected_activities = self._selected_workout_activities(workout_activities)
        workout_measure = self._selected_workout_measure()

        combined = pd.concat(
            [frame for frame in (steps_df, workouts_df) if not frame.empty],
            ignore_index=True,
        )
        if combined.empty:
            self._render_filters(workout_activities, year_options=[])
            st.warning("No activity data for the current selection.")
            return

        year_options = available_years(combined)
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
            self._render_filters(workout_activities, year_options=year_options)
            st.warning("No data for the selected years.")
            return

        if not steps_plot.empty:
            steps_source = self._repository.describe_steps_sources(steps_df)
            steps_period_label = "monthly" if steps_period == "monthly" else "weekly"
            st.markdown("#### Steps")
            st.caption(
                f"{steps_period_label.capitalize()} average of daily step totals from {steps_source}. "
                "When several sources report steps on the same day, Polar is preferred over "
                "Garmin, then other Apple Health sources. "
                f"{len(steps_plot)} points on chart."
            )
            period_col, _ = st.columns([1, 3])
            with period_col:
                render_period_filter(key="activity_steps_period")
            self._render_steps_chart(steps_plot, period=steps_period)

        if not workouts_plot.empty:
            workout_source = workouts_df.iloc[0]["source_name"]
            workout_period_label = "monthly" if workout_period == "monthly" else "weekly"
            measure_label = "workout count" if workout_measure == WORKOUT_MEASURE_COUNT else "duration"
            st.markdown("#### Workouts")
            st.caption(
                f"{workout_period_label.capitalize()} {measure_label} by activity from {workout_source}. "
                f"{len(selected_activities)} activities selected."
            )
            self._render_workout_chart(workouts_plot, period=workout_period, measure=workout_measure)

        if not steps_plot.empty:
            self._render_steps_summary(steps_plot)
        self._render_raw_data(steps_plot, workouts_plot)
        self._render_filters(workout_activities, year_options=year_options)

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
        """Render compact activity chart controls below the plots."""
        st.markdown("##### Chart options")

        if workout_activities:
            if year_options:
                year_col, period_col, measure_col = st.columns([2, 1, 1])
                with year_col:
                    render_year_filter(year_options, key="activity_years")
                with period_col:
                    render_period_filter(key="activity_workout_period")
                with measure_col:
                    st.radio(
                        "Show",
                        options=["Count", "Duration"],
                        horizontal=True,
                        key="activity_workout_measure",
                    )
            else:
                period_col, measure_col = st.columns([1, 1])
                with period_col:
                    render_period_filter(key="activity_workout_period")
                with measure_col:
                    st.radio(
                        "Show",
                        options=["Count", "Duration"],
                        horizontal=True,
                        key="activity_workout_measure",
                    )

            st.multiselect(
                "Activities",
                options=workout_activities,
                default=self._selected_workout_activities(workout_activities),
                help="Choose which activities appear as grouped columns on the workout chart.",
                key="activity_workout_activities",
            )
        elif year_options:
            render_year_period_row(
                year_options,
                year_key="activity_years",
                period_key="activity_workout_period",
            )

    def _render_steps_summary(self, df: pd.DataFrame) -> None:
        """Show the latest average step count."""
        latest = df.iloc[-1]
        st.metric("Steps", f"{latest['value']:,.0f}")

    def _render_steps_chart(self, df: pd.DataFrame, *, period: Period) -> None:
        """Plot step totals on a real y-axis."""
        chart = self._steps_chart.build(df, period=period)
        st.altair_chart(chart, use_container_width=True)

    def _render_workout_chart(
        self,
        df: pd.DataFrame,
        *,
        period: Period,
        measure: str,
    ) -> None:
        """Plot grouped workout bars by activity."""
        chart = self._workout_chart.build(df, period=period, measure=measure)
        st.altair_chart(chart, use_container_width=True)

    def _render_raw_data(
        self,
        steps_df: pd.DataFrame,
        workouts_df: pd.DataFrame,
    ) -> None:
        """Show the underlying chart data."""
        frames: list[pd.DataFrame] = []
        if not steps_df.empty:
            frames.append(steps_df.assign(series="Steps"))
        if not workouts_df.empty:
            frames.append(workouts_df.assign(series="Workouts"))

        if not frames:
            return

        with st.expander("Raw data"):
            st.dataframe(
                pd.concat(frames, ignore_index=True).sort_values(["series", "date"]),
                use_container_width=True,
            )
