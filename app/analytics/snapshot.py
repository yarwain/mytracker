"""Build a comparable summary of nutrition, training, and weight."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date, timedelta

import pandas as pd

from app.config import ANALYTICS_WINDOW_DAYS, PROTEIN_REFERENCE_G_PER_KG

_TOP_ACTIVITIES = 3
_MACRO_KCAL = (
    ("carb_kcal", "carbohydrates", 4.0),
    ("protein_kcal", "protein", 4.0),
    ("fat_kcal", "total_fat", 9.0),
)


@dataclass(frozen=True)
class WindowMetric:
    """One measurement for the current window and the previous window."""

    current: float | None
    previous: float | None

    @property
    def delta(self) -> float | None:
        """Return current minus previous when both sides are present."""
        if self.current is None or self.previous is None:
            return None
        return self.current - self.previous


@dataclass(frozen=True)
class ActivityTotal:
    """Workout totals for one activity inside a window."""

    activity: str
    sessions: int
    minutes: float


@dataclass(frozen=True)
class AnalyticsSnapshot:
    """Facts the dashboard shows and the only payload sent to the model."""

    as_of: date
    window_days: int
    current_start: date
    current_end: date
    previous_start: date
    previous_end: date
    protein_reference_g_per_kg: float
    nutrition_days: WindowMetric
    workout_days: WindowMetric
    weight_readings: WindowMetric
    avg_kcal: WindowMetric
    avg_protein_g: WindowMetric
    protein_g_per_kg: WindowMetric
    carb_share_pct: WindowMetric
    protein_share_pct: WindowMetric
    fat_share_pct: WindowMetric
    avg_energy_diff_kcal: WindowMetric
    surplus_days: WindowMetric
    deficit_days: WindowMetric
    workout_sessions: WindowMetric
    workout_minutes: WindowMetric
    avg_steps: WindowMetric
    top_activities: tuple[ActivityTotal, ...]
    previous_top_activities: tuple[ActivityTotal, ...]
    weight_change_kg: WindowMetric
    latest_weight_kg: float | None
    current_protein_basis_kg: float | None
    previous_protein_basis_kg: float | None

    def has_data(self) -> bool:
        """Return whether either window contains a logged series."""
        counts = (
            self.nutrition_days,
            self.workout_days,
            self.weight_readings,
            self.workout_sessions,
        )
        if any((metric.current or 0) > 0 or (metric.previous or 0) > 0 for metric in counts):
            return True
        averages = (
            self.avg_kcal,
            self.avg_protein_g,
            self.avg_energy_diff_kcal,
            self.avg_steps,
            self.weight_change_kg,
        )
        return any(metric.current is not None or metric.previous is not None for metric in averages)

    def to_payload(self) -> dict:
        """Return JSON-ready facts. Averages use logged days only."""
        return {
            "as_of": self.as_of.isoformat(),
            "window_days": self.window_days,
            "current_window": {
                "start": self.current_start.isoformat(),
                "end": self.current_end.isoformat(),
            },
            "previous_window": {
                "start": self.previous_start.isoformat(),
                "end": self.previous_end.isoformat(),
            },
            "protein_reference_g_per_kg": self.protein_reference_g_per_kg,
            "notes": [
                "Averages use logged days only.",
                "avg_diff_kcal is calories consumed minus calories spent. Positive is a surplus.",
                "Shares are the percent of carbohydrate, protein, and fat calories.",
                "protein_g_per_kg divides average protein by protein_basis_kg.",
                "protein_reference_g_per_kg is a comparison label, not a prescription.",
                "weight.change_kg is the last reading minus the first reading inside each window.",
            ],
            "coverage": {
                "nutrition_days": _metric_payload(self.nutrition_days, 0),
                "workout_days": _metric_payload(self.workout_days, 0),
                "weight_readings": _metric_payload(self.weight_readings, 0),
            },
            "nutrition": {
                "avg_kcal": _metric_payload(self.avg_kcal, 0),
                "avg_protein_g": _metric_payload(self.avg_protein_g, 1),
                "protein_g_per_kg": _metric_payload(self.protein_g_per_kg, 2),
                "protein_basis_kg": {
                    "current": _num(self.current_protein_basis_kg, 2),
                    "previous": _num(self.previous_protein_basis_kg, 2),
                },
                "carb_share_pct": _metric_payload(self.carb_share_pct, 1),
                "protein_share_pct": _metric_payload(self.protein_share_pct, 1),
                "fat_share_pct": _metric_payload(self.fat_share_pct, 1),
            },
            "energy": {
                "avg_diff_kcal": _metric_payload(self.avg_energy_diff_kcal, 0),
                "surplus_days": _metric_payload(self.surplus_days, 0),
                "deficit_days": _metric_payload(self.deficit_days, 0),
            },
            "training": {
                "sessions": _metric_payload(self.workout_sessions, 0),
                "minutes": _metric_payload(self.workout_minutes, 0),
                "avg_steps": _metric_payload(self.avg_steps, 0),
                "top_activities": {
                    "current": [_activity_payload(item) for item in self.top_activities],
                    "previous": [_activity_payload(item) for item in self.previous_top_activities],
                },
            },
            "weight": {
                "change_kg": _metric_payload(self.weight_change_kg, 2),
                "latest_kg": _num(self.latest_weight_kg, 2),
            },
        }

    def to_json(self) -> str:
        """Serialize the model payload."""
        return json.dumps(self.to_payload(), indent=2)

    def fingerprint(self) -> str:
        """Return a stable hash of the rounded payload."""
        encoded = json.dumps(self.to_payload(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(encoded.encode()).hexdigest()


class AnalyticsSnapshotBuilder:
    """Summarize daily repository frames for the current and previous windows."""

    def __init__(
        self,
        *,
        window_days: int = ANALYTICS_WINDOW_DAYS,
        protein_reference_g_per_kg: float = PROTEIN_REFERENCE_G_PER_KG,
    ) -> None:
        if window_days < 1:
            raise ValueError("window_days must be at least 1")
        self._window_days = window_days
        self._protein_reference_g_per_kg = protein_reference_g_per_kg

    def build(
        self,
        *,
        nutrition: pd.DataFrame | None = None,
        energy_balance: pd.DataFrame | None = None,
        workouts: pd.DataFrame | None = None,
        steps: pd.DataFrame | None = None,
        body_mass: pd.DataFrame | None = None,
        as_of: date | None = None,
    ) -> AnalyticsSnapshot:
        """Build a snapshot ending on as_of, inclusive.

        Frames match the repository loaders: one nutrition, energy, and steps row
        per day, and one workout row per day and activity. Duration is minutes,
        the same unit the workout chart plots.
        """
        as_of = as_of or date.today()
        current_start, current_end, previous_start, previous_end = window_bounds(
            as_of, self._window_days
        )
        nutrition_frame = _prepare(nutrition)
        energy_frame = _prepare(energy_balance)
        workout_frame = _prepare(workouts)
        steps_frame = _prepare(steps)
        weight_frame = _prepare(body_mass)
        weights = _weight_series(weight_frame)

        current_nutrition = _nutrition_window(_slice(nutrition_frame, current_start, current_end))
        previous_nutrition = _nutrition_window(
            _slice(nutrition_frame, previous_start, previous_end)
        )
        current_energy = _energy_window(_slice(energy_frame, current_start, current_end))
        previous_energy = _energy_window(_slice(energy_frame, previous_start, previous_end))
        current_workouts = _workout_window(_slice(workout_frame, current_start, current_end))
        previous_workouts = _workout_window(_slice(workout_frame, previous_start, previous_end))
        current_basis = _latest_on_or_before(weights, current_end)
        previous_basis = _latest_on_or_before(weights, previous_end)

        return AnalyticsSnapshot(
            as_of=as_of,
            window_days=self._window_days,
            current_start=current_start,
            current_end=current_end,
            previous_start=previous_start,
            previous_end=previous_end,
            protein_reference_g_per_kg=self._protein_reference_g_per_kg,
            nutrition_days=_metric(current_nutrition.days, previous_nutrition.days),
            workout_days=_metric(current_workouts.days, previous_workouts.days),
            weight_readings=_metric(
                _reading_count(weight_frame, current_start, current_end),
                _reading_count(weight_frame, previous_start, previous_end),
            ),
            avg_kcal=_metric(current_nutrition.avg_kcal, previous_nutrition.avg_kcal),
            avg_protein_g=_metric(
                current_nutrition.avg_protein_g, previous_nutrition.avg_protein_g
            ),
            protein_g_per_kg=_metric(
                _per_kg(current_nutrition.avg_protein_g, current_basis),
                _per_kg(previous_nutrition.avg_protein_g, previous_basis),
            ),
            carb_share_pct=_metric(
                current_nutrition.carb_share_pct, previous_nutrition.carb_share_pct
            ),
            protein_share_pct=_metric(
                current_nutrition.protein_share_pct, previous_nutrition.protein_share_pct
            ),
            fat_share_pct=_metric(
                current_nutrition.fat_share_pct, previous_nutrition.fat_share_pct
            ),
            avg_energy_diff_kcal=_metric(current_energy.avg_diff, previous_energy.avg_diff),
            surplus_days=_metric(current_energy.surplus_days, previous_energy.surplus_days),
            deficit_days=_metric(current_energy.deficit_days, previous_energy.deficit_days),
            workout_sessions=_metric(current_workouts.sessions, previous_workouts.sessions),
            workout_minutes=_metric(current_workouts.minutes, previous_workouts.minutes),
            avg_steps=_metric(
                _mean(_slice(steps_frame, current_start, current_end), "value"),
                _mean(_slice(steps_frame, previous_start, previous_end), "value"),
            ),
            top_activities=current_workouts.top_activities,
            previous_top_activities=previous_workouts.top_activities,
            weight_change_kg=_metric(
                _weight_change(weights, current_start, current_end),
                _weight_change(weights, previous_start, previous_end),
            ),
            latest_weight_kg=current_basis,
            current_protein_basis_kg=current_basis,
            previous_protein_basis_kg=previous_basis,
        )


def window_bounds(as_of: date, window_days: int) -> tuple[date, date, date, date]:
    """Return current and previous inclusive date ranges."""
    if window_days < 1:
        raise ValueError("window_days must be at least 1")
    current_end = as_of
    current_start = as_of - timedelta(days=window_days - 1)
    previous_end = current_start - timedelta(days=1)
    previous_start = previous_end - timedelta(days=window_days - 1)
    return current_start, current_end, previous_start, previous_end


@dataclass(frozen=True)
class _NutritionWindow:
    days: float
    avg_kcal: float | None
    avg_protein_g: float | None
    carb_share_pct: float | None
    protein_share_pct: float | None
    fat_share_pct: float | None


@dataclass(frozen=True)
class _EnergyWindow:
    avg_diff: float | None
    surplus_days: float
    deficit_days: float


@dataclass(frozen=True)
class _WorkoutWindow:
    days: float
    sessions: float | None
    minutes: float | None
    top_activities: tuple[ActivityTotal, ...]


def _metric(current: float | None, previous: float | None) -> WindowMetric:
    return WindowMetric(current=current, previous=previous)


def _prepare(frame: pd.DataFrame | None, date_column: str = "date") -> pd.DataFrame:
    if frame is None or frame.empty or date_column not in frame.columns:
        return pd.DataFrame()
    prepared = frame.copy()
    parsed = pd.to_datetime(prepared[date_column], errors="coerce")
    valid = parsed.notna()
    prepared = prepared.loc[valid].copy()
    if prepared.empty:
        return pd.DataFrame()
    prepared[date_column] = parsed.loc[valid].dt.date
    return prepared


def _slice(frame: pd.DataFrame, start: date, end: date) -> pd.DataFrame:
    if frame.empty:
        return frame
    dates = frame["date"]
    return frame.loc[(dates >= start) & (dates <= end)].copy()


def _mean(frame: pd.DataFrame, column: str) -> float | None:
    if frame.empty or column not in frame.columns:
        return None
    series = pd.to_numeric(frame[column], errors="coerce").dropna()
    if series.empty:
        return None
    return float(series.mean())


def _nutrition_window(frame: pd.DataFrame) -> _NutritionWindow:
    carb_share, protein_share, fat_share = _macro_shares(frame)
    days = 0.0 if frame.empty else float(frame["date"].nunique())
    return _NutritionWindow(
        days=days,
        avg_kcal=_mean(frame, "calories"),
        avg_protein_g=_mean(frame, "protein"),
        carb_share_pct=carb_share,
        protein_share_pct=protein_share,
        fat_share_pct=fat_share,
    )


def _macro_shares(frame: pd.DataFrame) -> tuple[float | None, float | None, float | None]:
    if frame.empty:
        return (None, None, None)
    totals = [
        _kcal_sum(frame, column, grams_column, factor)
        for column, grams_column, factor in _MACRO_KCAL
    ]
    total = sum(totals)
    if total <= 0:
        return (None, None, None)
    return tuple(100.0 * value / total for value in totals)


def _kcal_sum(frame: pd.DataFrame, column: str, grams_column: str, factor: float) -> float:
    if column in frame.columns:
        values = pd.to_numeric(frame[column], errors="coerce")
        if values.notna().any():
            return float(values.fillna(0).sum())
    if grams_column not in frame.columns:
        return 0.0
    grams = pd.to_numeric(frame[grams_column], errors="coerce").fillna(0)
    return float((grams * factor).sum())


def _energy_window(frame: pd.DataFrame) -> _EnergyWindow:
    if frame.empty or "diff_kcal" not in frame.columns:
        return _EnergyWindow(avg_diff=None, surplus_days=0.0, deficit_days=0.0)
    diff = pd.to_numeric(frame["diff_kcal"], errors="coerce").dropna()
    if diff.empty:
        return _EnergyWindow(avg_diff=None, surplus_days=0.0, deficit_days=0.0)
    return _EnergyWindow(
        avg_diff=float(diff.mean()),
        surplus_days=float((diff > 0).sum()),
        deficit_days=float((diff < 0).sum()),
    )


def _workout_window(frame: pd.DataFrame) -> _WorkoutWindow:
    if frame.empty:
        return _empty_workouts()
    work = frame.copy()
    if "activity" not in work.columns:
        if "activity_type" not in work.columns:
            return _empty_workouts()
        work["activity"] = work["activity_type"]
    work = work.dropna(subset=["activity"])
    work["activity"] = work["activity"].map(lambda value: str(value).strip())
    work = work[work["activity"] != ""]
    if work.empty:
        return _empty_workouts()
    if "workout_count" not in work.columns:
        work["workout_count"] = 1
    if "total_duration" not in work.columns:
        work["total_duration"] = work["duration"] if "duration" in work.columns else 0
    work["workout_count"] = pd.to_numeric(work["workout_count"], errors="coerce").fillna(0)
    work["total_duration"] = pd.to_numeric(work["total_duration"], errors="coerce").fillna(0)
    active = work[work["workout_count"] > 0]
    days = float(active["date"].nunique()) if not active.empty else 0.0
    return _WorkoutWindow(
        days=days,
        sessions=float(work["workout_count"].sum()),
        minutes=float(work["total_duration"].sum()),
        top_activities=_top_activities(work),
    )


def _empty_workouts() -> _WorkoutWindow:
    return _WorkoutWindow(days=0.0, sessions=0.0, minutes=0.0, top_activities=())


def _top_activities(frame: pd.DataFrame) -> tuple[ActivityTotal, ...]:
    grouped = (
        frame.groupby("activity", as_index=False)
        .agg(sessions=("workout_count", "sum"), minutes=("total_duration", "sum"))
        .sort_values(["minutes", "sessions", "activity"], ascending=[False, False, True])
    )
    totals: list[ActivityTotal] = []
    for row in grouped.head(_TOP_ACTIVITIES).itertuples(index=False):
        totals.append(
            ActivityTotal(
                activity=str(row.activity),
                sessions=int(row.sessions),
                minutes=float(row.minutes),
            )
        )
    return tuple(totals)


def _weight_series(frame: pd.DataFrame) -> pd.Series:
    if frame.empty or "value" not in frame.columns:
        return pd.Series(dtype=float)
    work = frame.copy()
    work["value"] = pd.to_numeric(work["value"], errors="coerce")
    work = work.dropna(subset=["value"]).sort_values("date")
    if work.empty:
        return pd.Series(dtype=float)
    return work.groupby("date")["value"].last().sort_index()


def _weight_change(weights: pd.Series, start: date, end: date) -> float | None:
    if weights.empty:
        return None
    window = weights[(weights.index >= start) & (weights.index <= end)]
    if len(window) < 2:
        return None
    return float(window.iloc[-1] - window.iloc[0])


def _latest_on_or_before(weights: pd.Series, day: date) -> float | None:
    if weights.empty:
        return None
    prior = weights[weights.index <= day]
    if prior.empty:
        return None
    return float(prior.iloc[-1])


def _reading_count(frame: pd.DataFrame, start: date, end: date) -> float:
    return float(len(_slice(frame, start, end)))


def _per_kg(avg_protein_g: float | None, weight_kg: float | None) -> float | None:
    if avg_protein_g is None or weight_kg is None or weight_kg <= 0:
        return None
    return avg_protein_g / weight_kg


def _num(value: float | None, digits: int) -> int | float | None:
    if value is None:
        return None
    rounded = round(float(value), digits)
    if digits == 0:
        return int(rounded)
    return rounded


def _metric_payload(metric: WindowMetric, digits: int) -> dict[str, int | float | None]:
    current = _num(metric.current, digits)
    previous = _num(metric.previous, digits)
    delta = None
    if current is not None and previous is not None:
        delta = _num(float(current) - float(previous), digits)
    return {"current": current, "previous": previous, "delta": delta}


def _activity_payload(activity: ActivityTotal) -> dict[str, str | int]:
    return {
        "activity": activity.activity,
        "sessions": activity.sessions,
        "minutes": int(round(activity.minutes)),
    }
