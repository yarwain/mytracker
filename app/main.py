"""Streamlit entry point for MyTracker."""

import streamlit as st

from app.database import Database
from app.repositories.manual_metrics_repository import ManualMetricsRepository
from app.repositories.zepp_repository import ZeppRepository
from app.views.manual_metrics_view import ManualMetricsView
from app.views.zepp_metrics_view import ZeppMetricsView


class MyTrackerApp:
    """Top-level Streamlit application."""

    def __init__(self, database: Database | None = None) -> None:
        self._database = database or Database()
        self._zepp_view = ZeppMetricsView(ZeppRepository(self._database))
        self._manual_view = ManualMetricsView(ManualMetricsRepository(self._database))

    def run(self) -> None:
        """Render the dashboard."""
        st.set_page_config(page_title="MyTracker", layout="wide")
        st.title("MyTracker")
        st.caption("Health statistics from Apple Health, Garmin, and FatSecret")

        if not self._database.exists:
            st.info(f"No database yet. Import data to create `{self._database.db_path}`.")
            return

        self._database.ensure_schema()

        self._manual_view.render()
        st.divider()
        self._zepp_view.render()


def main() -> None:
    """Run the Streamlit application."""
    MyTrackerApp().run()


if __name__ == "__main__":
    main()
