"""Streamlit entry point for MyTracker."""

import streamlit as st

from app.database import Database
from app.repositories.activity_repository import ActivityRepository
from app.repositories.body_mass_repository import BodyMassRepository
from app.repositories.manual_metrics_repository import ManualMetricsRepository
from app.repositories.nutrition_repository import NutritionRepository
from app.repositories.zepp_repository import ZeppRepository
from app.views.activity_view import ActivityView
from app.views.analytics_view import AnalyticsView
from app.views.manual_metrics_view import ManualMetricsView
from app.views.nutrition_view import NutritionView


class MyTrackerApp:
    """Top-level Streamlit application."""

    def __init__(self, database: Database | None = None) -> None:
        self._database = database or Database()
        manual_repository = ManualMetricsRepository(self._database)
        zepp_repository = ZeppRepository(self._database)
        body_mass_repository = BodyMassRepository(
            manual_repository=manual_repository,
            zepp_repository=zepp_repository,
        )
        self._body_view = ManualMetricsView(
            manual_repository,
            zepp_repository,
            body_mass_repository,
        )
        self._nutrition_view = NutritionView(
            NutritionRepository(self._database),
            zepp_repository,
            body_mass_repository=body_mass_repository,
        )
        self._activity_view = ActivityView(ActivityRepository(self._database))
        self._analytics_view = AnalyticsView(
            nutrition_repository=NutritionRepository(self._database),
            activity_repository=ActivityRepository(self._database),
            body_mass_repository=body_mass_repository,
        )

    def run(self) -> None:
        """Render the dashboard."""
        st.set_page_config(page_title="MyTracker", layout="wide", initial_sidebar_state="collapsed")
        st.title("MyTracker")

        if not self._database.exists:
            st.info(f"No database yet. Import data to create `{self._database.db_path}`.")
            return

        self._database.ensure_schema()

        self._body_view.render()
        st.divider()
        self._nutrition_view.render()
        st.divider()
        self._activity_view.render()
        st.divider()
        self._analytics_view.render()


def main() -> None:
    """Run the Streamlit application."""
    MyTrackerApp().run()


if __name__ == "__main__":
    main()
