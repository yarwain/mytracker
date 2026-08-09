"""Shared body mass series from manual weight and Zepp readings."""

import pandas as pd

from app.config import BODY_MASS_METRIC, MANUAL_METRIC_BY_KEY, ZEPP_SOURCE
from app.database import Database
from app.repositories.manual_metrics_repository import ManualMetricsRepository
from app.repositories.zepp_repository import ZeppRepository

MANUAL_WEIGHT_METRIC = MANUAL_METRIC_BY_KEY["weight"]
BODY_MASS_COLUMNS = ["date", "value", "unit", "label", "reading_count", "source_name"]


class BodyMassRepository:
    """Load one daily body mass series, preferring manual weight over Zepp."""

    def __init__(
        self,
        database: Database | None = None,
        manual_repository: ManualMetricsRepository | None = None,
        zepp_repository: ZeppRepository | None = None,
    ) -> None:
        if manual_repository is not None:
            database = manual_repository._database
        if zepp_repository is not None and database is None:
            database = zepp_repository._database
        database = database or Database()
        self._manual = manual_repository or ManualMetricsRepository(database)
        self._zepp = zepp_repository or ZeppRepository(database)

    def has_data(self) -> bool:
        """Return whether manual weight or Zepp body mass exists."""
        manual = self._manual.load_metrics([MANUAL_WEIGHT_METRIC])
        if not manual.empty:
            return True
        return BODY_MASS_METRIC in self._zepp.list_available_metrics()

    def load_daily(self) -> pd.DataFrame:
        """Return unified daily body mass with manual entries taking priority."""
        manual = self._manual.load_metrics([MANUAL_WEIGHT_METRIC])
        manual_part = pd.DataFrame(columns=BODY_MASS_COLUMNS)
        if not manual.empty:
            manual_part = manual.copy()
            manual_part["source_name"] = "manual"
            if "reading_count" not in manual_part.columns:
                manual_part["reading_count"] = 1

        zepp_part = pd.DataFrame(columns=BODY_MASS_COLUMNS)
        if BODY_MASS_METRIC in self._zepp.list_available_metrics():
            zepp_daily = self._zepp.load_daily_metric(BODY_MASS_METRIC)
            if not zepp_daily.empty:
                zepp_part = zepp_daily.copy()
                zepp_part["label"] = BODY_MASS_METRIC.label
                zepp_part["source_name"] = ZEPP_SOURCE

        if manual_part.empty and zepp_part.empty:
            return pd.DataFrame(columns=BODY_MASS_COLUMNS)

        if manual_part.empty:
            return zepp_part.sort_values("date").reset_index(drop=True)
        if zepp_part.empty:
            return manual_part.sort_values("date").reset_index(drop=True)

        manual_part["date"] = pd.to_datetime(manual_part["date"]).dt.date
        zepp_part["date"] = pd.to_datetime(zepp_part["date"]).dt.date
        manual_dates = set(manual_part["date"])
        zepp_only = zepp_part[~zepp_part["date"].isin(manual_dates)]
        combined = pd.concat([manual_part, zepp_only], ignore_index=True)
        return combined.sort_values("date").reset_index(drop=True)
