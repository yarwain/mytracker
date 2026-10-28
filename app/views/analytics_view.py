"""Streamlit view for local analytics facts and an optional written review."""

from datetime import date

import streamlit as st

from app.analytics.review import (
    AnalyticsReview,
    AnalyticsReviewError,
    AnalyticsReviewer,
    MissingApiKeyError,
)
from app.analytics.snapshot import AnalyticsSnapshot, AnalyticsSnapshotBuilder, WindowMetric
from app.repositories.activity_repository import ActivityRepository
from app.repositories.body_mass_repository import BodyMassRepository
from app.repositories.energy_balance_repository import EnergyBalanceRepository
from app.repositories.nutrition_repository import NutritionRepository

_REVIEW_KEY = "analytics_review"
_REVIEW_FINGERPRINT_KEY = "analytics_review_fingerprint"


class AnalyticsView:
    """Render fact cards, then a review generated from those facts."""

    def __init__(
        self,
        nutrition_repository: NutritionRepository | None = None,
        activity_repository: ActivityRepository | None = None,
        energy_balance_repository: EnergyBalanceRepository | None = None,
        body_mass_repository: BodyMassRepository | None = None,
        reviewer: AnalyticsReviewer | None = None,
        as_of: date | None = None,
    ) -> None:
        self._nutrition = nutrition_repository or NutritionRepository()
        self._activity = activity_repository or ActivityRepository()
        self._energy = energy_balance_repository or EnergyBalanceRepository(
            activity_repository=self._activity,
            nutrition_repository=self._nutrition,
        )
        self._body_mass = body_mass_repository or BodyMassRepository()
        self._builder = AnalyticsSnapshotBuilder()
        self._reviewer = reviewer or AnalyticsReviewer()
        self._as_of = as_of

    def render(self) -> None:
        """Draw the analytics section."""
        st.subheader("Analytics")
        snapshot = self._builder.build(
            nutrition=self._nutrition.load_macro_calorie_breakdown(),
            energy_balance=self._energy.load_daily_balance(),
            workouts=self._activity.load_workout_breakdown(),
            steps=self._activity.load_steps(),
            body_mass=self._body_mass.load_daily(),
            as_of=self._as_of,
        )
        st.caption(
            f"{_fmt_day(snapshot.current_start)} – {_fmt_day(snapshot.current_end)} "
            f"compared with {_fmt_day(snapshot.previous_start)} – "
            f"{_fmt_day(snapshot.previous_end)}."
        )
        if not snapshot.has_data():
            st.warning(f"No nutrition or training data in the last {snapshot.window_days} days.")
            return

        _render_facts(snapshot)
        _render_review(snapshot, self._reviewer)


def _render_facts(snapshot: AnalyticsSnapshot) -> None:
    st.markdown("**Coverage**")
    _metric_row(
        [
            ("Nutrition days", snapshot.nutrition_days, 0, ""),
            ("Workout days", snapshot.workout_days, 0, ""),
            ("Weight readings", snapshot.weight_readings, 0, ""),
        ]
    )

    st.markdown("**Nutrition**")
    _metric_row(
        [
            ("Avg calories", snapshot.avg_kcal, 0, " kcal"),
            ("Protein", snapshot.avg_protein_g, 1, " g"),
            ("Protein per kg", snapshot.protein_g_per_kg, 2, " g/kg"),
        ]
    )
    _metric_row(
        [
            ("Carb share", snapshot.carb_share_pct, 1, "%"),
            ("Protein share", snapshot.protein_share_pct, 1, "%"),
            ("Fat share", snapshot.fat_share_pct, 1, "%"),
        ]
    )
    reference = f"{snapshot.protein_reference_g_per_kg:g}"
    st.caption(
        "Protein per kg divides average protein by the latest weight on or before "
        f"the end of each window. The comparison label is {reference} g/kg."
    )

    st.markdown("**Energy**")
    _metric_row(
        [
            ("Avg energy balance", snapshot.avg_energy_diff_kcal, 0, " kcal", True),
            ("Surplus days", snapshot.surplus_days, 0, ""),
            ("Deficit days", snapshot.deficit_days, 0, ""),
        ]
    )
    st.caption(
        "Energy balance is calories consumed minus calories spent, averaged on days that have both."
    )

    st.markdown("**Training**")
    _metric_row(
        [
            ("Sessions", snapshot.workout_sessions, 0, ""),
            ("Minutes", snapshot.workout_minutes, 0, " min"),
            ("Avg steps", snapshot.avg_steps, 0, ""),
        ]
    )
    _render_activities(snapshot.top_activities)

    st.markdown("**Weight**")
    change, latest = st.columns(2)
    with change:
        _show_metric(
            "Weight change",
            snapshot.weight_change_kg,
            digits=2,
            suffix=" kg",
            signed=True,
        )
    with latest:
        st.metric(
            "Latest weight",
            _fmt_value(snapshot.latest_weight_kg, digits=2, suffix=" kg"),
        )
    st.caption("Weight change is the last reading minus the first reading inside each window.")


def _render_activities(activities: tuple) -> None:
    if not activities:
        st.caption("No workouts in this window.")
        return
    st.markdown("**Top activities**")
    lines = []
    for activity in activities:
        label = "session" if activity.sessions == 1 else "sessions"
        lines.append(
            f"- {activity.activity}: {activity.sessions} {label}, {activity.minutes:,.0f} min"
        )
    st.markdown("\n".join(lines))


def _render_review(snapshot: AnalyticsSnapshot, reviewer: AnalyticsReviewer) -> None:
    st.markdown("**Review**")
    st.caption("Write a review from these facts. The request sends the summary, not diary rows.")
    if not reviewer.api_key_configured:
        st.info(
            "Set OPENAI_API_KEY to generate a written review. "
            "The fact cards above stay on this machine."
        )

    fingerprint = snapshot.fingerprint()
    cached = st.session_state.get(_REVIEW_KEY)
    cached_fingerprint = st.session_state.get(_REVIEW_FINGERPRINT_KEY)
    if st.button(
        "Write review",
        key="analytics_write_review",
        disabled=not reviewer.api_key_configured,
    ):
        try:
            review = reviewer.review(snapshot)
        except MissingApiKeyError:
            st.info("Set OPENAI_API_KEY to generate a written review.")
        except AnalyticsReviewError as exc:
            st.error(str(exc))
        else:
            st.session_state[_REVIEW_KEY] = review
            st.session_state[_REVIEW_FINGERPRINT_KEY] = fingerprint
            cached = review
            cached_fingerprint = fingerprint

    if isinstance(cached, AnalyticsReview) and cached_fingerprint == fingerprint:
        _render_review_body(cached)


def _render_review_body(review: AnalyticsReview) -> None:
    with st.container(border=True):
        st.markdown(f"**{review.headline}**")
        for observation in review.observations:
            st.markdown(f"- {observation}")
        st.markdown("**Suggestions**")
        for suggestion in review.suggestions:
            st.markdown(f"- **{suggestion.title}.** {suggestion.detail}")
        st.caption("This review summarizes your logged data. It is not medical advice.")


def _metric_row(items: list[tuple]) -> None:
    columns = st.columns(len(items))
    for column, item in zip(columns, items, strict=True):
        label, metric, digits, suffix = item[:4]
        signed = bool(item[4]) if len(item) > 4 else False
        with column:
            _show_metric(label, metric, digits=digits, suffix=suffix, signed=signed)


def _show_metric(
    label: str,
    metric: WindowMetric,
    *,
    digits: int,
    suffix: str,
    signed: bool = False,
) -> None:
    st.metric(
        label,
        _fmt_value(metric.current, digits=digits, suffix=suffix, signed=signed),
        delta=_fmt_delta(metric.delta, digits=digits, suffix=suffix),
        delta_color="off",
    )


def _fmt_day(value: date) -> str:
    return f"{value.day} {_month(value)} {value.year}"


def _month(value: date) -> str:
    return value.strftime("%b")


def _fmt_value(
    value: float | None,
    *,
    digits: int,
    suffix: str = "",
    signed: bool = False,
) -> str:
    if value is None:
        return "—"
    if digits == 0:
        number = f"{value:+,.0f}" if signed else f"{value:,.0f}"
    else:
        number = f"{value:+,.{digits}f}" if signed else f"{value:,.{digits}f}"
    return f"{number}{suffix}"


def _fmt_delta(value: float | None, *, digits: int, suffix: str) -> str | None:
    if value is None:
        return None
    return _fmt_value(value, digits=digits, suffix=suffix, signed=True)
