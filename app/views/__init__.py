"""Streamlit views for health charts."""

from app.views.activity_view import ActivityView
from app.views.manual_metrics_view import ManualMetricsView
from app.views.nutrition_view import NutritionView

__all__ = ["ActivityView", "ManualMetricsView", "NutritionView"]
