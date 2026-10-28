from datetime import date

import pandas as pd
import pytest

from app.analytics.snapshot import AnalyticsSnapshotBuilder
from app.config import PROTEIN_REFERENCE_G_PER_KG

AS_OF = date(2026, 10, 18)


def test_snapshot_compares_current_window_with_previous_window() -> None:
    snapshot = AnalyticsSnapshotBuilder().build(
        nutrition=_nutrition(),
        energy_balance=_energy(),
        workouts=_workouts(),
        steps=_steps(),
        body_mass=_weights(),
        as_of=AS_OF,
    )

    assert snapshot.current_start == date(2026, 9, 21)
    assert snapshot.current_end == AS_OF
    assert snapshot.previous_start == date(2026, 8, 24)
    assert snapshot.previous_end == date(2026, 9, 20)
    assert snapshot.protein_reference_g_per_kg == PROTEIN_REFERENCE_G_PER_KG

    assert snapshot.nutrition_days.current == 3
    assert snapshot.nutrition_days.previous == 2
    assert snapshot.nutrition_days.delta == 1
    assert snapshot.avg_kcal.current == pytest.approx(2000)
    assert snapshot.avg_kcal.previous == pytest.approx(1700)
    assert snapshot.avg_kcal.delta == pytest.approx(300)
    assert snapshot.avg_protein_g.current == pytest.approx(100)
    assert snapshot.avg_protein_g.previous == pytest.approx(90)
    assert snapshot.avg_protein_g.delta == pytest.approx(10)
    assert snapshot.protein_g_per_kg.current == pytest.approx(100 / 58)
    assert snapshot.protein_g_per_kg.previous == pytest.approx(90 / 60)
    assert snapshot.current_protein_basis_kg == pytest.approx(58)
    assert snapshot.previous_protein_basis_kg == pytest.approx(60)
    assert snapshot.carb_share_pct.current == pytest.approx(2360 / 4910 * 100)
    assert snapshot.protein_share_pct.current == pytest.approx(1200 / 4910 * 100)
    assert snapshot.fat_share_pct.current == pytest.approx(1350 / 4910 * 100)
    assert snapshot.carb_share_pct.previous == pytest.approx(1280 / 2810 * 100)

    assert snapshot.avg_energy_diff_kcal.current == pytest.approx(-50)
    assert snapshot.avg_energy_diff_kcal.previous == pytest.approx(50)
    assert snapshot.avg_energy_diff_kcal.delta == pytest.approx(-100)
    assert snapshot.surplus_days.current == 1
    assert snapshot.surplus_days.previous == 1
    assert snapshot.surplus_days.delta == 0
    assert snapshot.deficit_days.current == 2
    assert snapshot.deficit_days.previous == 0
    assert snapshot.deficit_days.delta == 2

    assert snapshot.workout_days.current == 2
    assert snapshot.workout_days.previous == 1
    assert snapshot.workout_sessions.current == 4
    assert snapshot.workout_sessions.previous == 1
    assert snapshot.workout_sessions.delta == 3
    assert snapshot.workout_minutes.current == pytest.approx(160)
    assert snapshot.workout_minutes.previous == pytest.approx(20)
    assert snapshot.workout_minutes.delta == pytest.approx(140)
    assert [(item.activity, item.sessions, item.minutes) for item in snapshot.top_activities] == [
        ("Cycling", 1, 90.0),
        ("Running", 3, 70.0),
    ]
    assert snapshot.previous_top_activities[0].activity == "Running"
    assert snapshot.previous_top_activities[0].sessions == 1

    assert snapshot.avg_steps.current == pytest.approx(9000)
    assert snapshot.avg_steps.previous == pytest.approx(7000)
    assert snapshot.avg_steps.delta == pytest.approx(2000)

    assert snapshot.weight_readings.current == 2
    assert snapshot.weight_readings.previous == 2
    assert snapshot.weight_change_kg.current == pytest.approx(-2)
    assert snapshot.weight_change_kg.previous == pytest.approx(-2)
    assert snapshot.weight_change_kg.delta == pytest.approx(0)
    assert snapshot.latest_weight_kg == pytest.approx(58)

    payload = snapshot.to_payload()
    assert payload["nutrition"]["avg_kcal"]["delta"] == 300
    assert payload["weight"]["latest_kg"] == 58
    assert (
        snapshot.fingerprint()
        == AnalyticsSnapshotBuilder()
        .build(
            nutrition=_nutrition(),
            energy_balance=_energy(),
            workouts=_workouts(),
            steps=_steps(),
            body_mass=_weights(),
            as_of=AS_OF,
        )
        .fingerprint()
    )


def test_sparse_window_averages_logged_days_and_derives_shares_from_grams() -> None:
    snapshot = AnalyticsSnapshotBuilder().build(
        nutrition=pd.DataFrame(
            [
                {
                    "date": date(2026, 10, 1),
                    "calories": 1500,
                    "protein": 75,
                    "carbohydrates": 100,
                    "total_fat": 50,
                }
            ]
        ),
        body_mass=pd.DataFrame([{"date": date(2026, 10, 1), "value": 50}]),
        as_of=AS_OF,
    )

    assert snapshot.has_data()
    assert snapshot.nutrition_days.current == 1
    assert snapshot.nutrition_days.previous == 0
    assert snapshot.avg_kcal.current == pytest.approx(1500)
    assert snapshot.avg_kcal.previous is None
    assert snapshot.avg_kcal.delta is None
    assert snapshot.protein_g_per_kg.current == pytest.approx(1.5)
    assert snapshot.protein_g_per_kg.previous is None
    assert snapshot.carb_share_pct.current == pytest.approx(400 / 1150 * 100)
    assert snapshot.protein_share_pct.current == pytest.approx(300 / 1150 * 100)
    assert snapshot.fat_share_pct.current == pytest.approx(450 / 1150 * 100)
    assert snapshot.weight_readings.current == 1
    assert snapshot.weight_change_kg.current is None
    assert snapshot.latest_weight_kg == pytest.approx(50)
    assert snapshot.workout_sessions.current == 0
    assert snapshot.to_payload()["nutrition"]["avg_kcal"]["previous"] is None
    assert snapshot.to_payload()["coverage"]["nutrition_days"] == {
        "current": 1,
        "previous": 0,
        "delta": 1,
    }


def test_empty_snapshot_has_no_data() -> None:
    snapshot = AnalyticsSnapshotBuilder().build(as_of=AS_OF)
    assert snapshot.has_data() is False
    assert snapshot.avg_kcal.current is None
    assert snapshot.nutrition_days.current == 0
    assert snapshot.to_payload()["energy"]["avg_diff_kcal"]["current"] is None


def test_week_window_bounds() -> None:
    snapshot = AnalyticsSnapshotBuilder(window_days=7).build(as_of=AS_OF)
    assert snapshot.current_start == date(2026, 10, 12)
    assert snapshot.current_end == AS_OF
    assert snapshot.previous_end == date(2026, 10, 11)
    assert snapshot.previous_start == date(2026, 10, 5)


def test_window_days_must_be_positive() -> None:
    with pytest.raises(ValueError, match="window_days"):
        AnalyticsSnapshotBuilder(window_days=0)


def _nutrition() -> pd.DataFrame:
    rows = [
        _meal(date(2026, 8, 23), 9999, 1, 1, 1),
        _meal(date(2026, 8, 24), 1600, 80, 150, 40),
        _meal(date(2026, 9, 20), 1800, 100, 170, 50),
        _meal(date(2026, 9, 21), 2000, 100, 200, 50),
        _meal(date(2026, 10, 1), 2200, 110, 210, 60),
        _meal(date(2026, 10, 18), 1800, 90, 180, 40),
        _meal(date(2026, 10, 19), 9999, 1, 1, 1),
    ]
    frame = pd.DataFrame(rows)
    frame["carb_kcal"] = frame["carbohydrates"] * 4
    frame["protein_kcal"] = frame["protein"] * 4
    frame["fat_kcal"] = frame["total_fat"] * 9
    return frame


def _meal(day: date, calories: float, protein: float, carbohydrates: float, fat: float) -> dict:
    return {
        "date": day,
        "calories": calories,
        "protein": protein,
        "carbohydrates": carbohydrates,
        "total_fat": fat,
    }


def _energy() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"date": date(2026, 8, 23), "diff_kcal": 500},
            {"date": date(2026, 8, 24), "diff_kcal": 50},
            {"date": date(2026, 9, 21), "diff_kcal": 100},
            {"date": date(2026, 10, 1), "diff_kcal": -200},
            {"date": date(2026, 10, 2), "diff_kcal": None},
            {"date": date(2026, 10, 10), "diff_kcal": -50},
        ]
    )


def _workouts() -> pd.DataFrame:
    return pd.DataFrame(
        [
            _workout(date(2026, 8, 23), "Running", 10, 500),
            _workout(date(2026, 8, 25), "Running", 1, 20),
            _workout(date(2026, 9, 22), "Running", 2, 40),
            _workout(date(2026, 10, 5), "Cycling", 1, 90),
            _workout(date(2026, 10, 5), "Running", 1, 30),
        ]
    )


def _workout(day: date, activity: str, count: int, minutes: float) -> dict:
    return {
        "date": day,
        "activity": activity,
        "workout_count": count,
        "total_duration": minutes,
    }


def _steps() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"date": date(2026, 1, 1), "value": 100},
            {"date": date(2026, 8, 24), "value": 7000},
            {"date": date(2026, 9, 21), "value": 8000},
            {"date": date(2026, 9, 22), "value": 10000},
        ]
    )


def _weights() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"date": date(2026, 7, 1), "value": 70},
            {"date": date(2026, 8, 24), "value": 62},
            {"date": date(2026, 9, 20), "value": 60},
            {"date": date(2026, 9, 21), "value": 60},
            {"date": date(2026, 10, 18), "value": 58},
            {"date": date(2026, 10, 19), "value": 40},
        ]
    )
