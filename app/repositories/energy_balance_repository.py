"""Repository for daily calories spent vs consumed."""

import pandas as pd

from app.database import Database
from app.repositories.activity_repository import ActivityRepository
from app.repositories.nutrition_repository import NutritionRepository


def energy_balance_diff(consumed: pd.Series, spent: pd.Series) -> pd.Series:
    """Return consumed minus spent, omitting periods without logged intake."""
    diff = consumed - spent
    missing_consumed = consumed.isna() | (consumed <= 0)
    return diff.where(~missing_consumed)


class EnergyBalanceRepository:
    """Combine Polar/Garmin energy burned with meal-log calories consumed."""

    def __init__(
        self,
        database: Database | None = None,
        activity_repository: ActivityRepository | None = None,
        nutrition_repository: NutritionRepository | None = None,
    ) -> None:
        if nutrition_repository is not None:
            database = nutrition_repository._database
        if activity_repository is not None and database is None:
            database = activity_repository._database
        database = database or Database()
        self._activity = activity_repository or ActivityRepository(database)
        self._nutrition = nutrition_repository or NutritionRepository(database)

    def has_data(self, *, sources: list[str] | None = None) -> bool:
        """Return whether either spent or consumed calorie data exists."""
        return self._activity.has_energy_data() or self._has_consumed_data(sources=sources)

    def load_daily_balance(self, *, sources: list[str] | None = None) -> pd.DataFrame:
        """Load merged daily spent, consumed, and diff calories."""
        spent = self._activity.load_daily_energy_burned()
        breakdown = self._nutrition.load_macro_calorie_breakdown(sources=sources)

        spent_part = pd.DataFrame(columns=["date", "spent_kcal", "spent_source"])
        if not spent.empty:
            spent_part = spent.rename(columns={"value": "spent_kcal"})[
                ["date", "spent_kcal", "source_name"]
            ].rename(columns={"source_name": "spent_source"})

        consumed_part = pd.DataFrame(columns=["date", "consumed_kcal"])
        if not breakdown.empty:
            consumed_part = breakdown[["date", "calories"]].rename(columns={"calories": "consumed_kcal"})

        if spent_part.empty and consumed_part.empty:
            return pd.DataFrame(
                columns=["date", "spent_kcal", "consumed_kcal", "diff_kcal", "spent_source"]
            )

        balance = spent_part.merge(consumed_part, on="date", how="outer")
        balance["diff_kcal"] = energy_balance_diff(
            balance["consumed_kcal"],
            balance["spent_kcal"],
        )
        balance["date"] = pd.to_datetime(balance["date"]).dt.date
        return balance.sort_values("date").reset_index(drop=True)

    def _has_consumed_data(self, *, sources: list[str] | None = None) -> bool:
        breakdown = self._nutrition.load_macro_calorie_breakdown(sources=sources)
        return not breakdown.empty
