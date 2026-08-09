"""Application configuration and Apple Health metric identifiers."""

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class MorningWindow:
    """Local-time hour range used to classify morning measurements."""

    start_hour: int = 5
    end_hour: int = 11

    def label(self) -> str:
        """Return a human-readable label for the configured window."""
        return f"{self.start_hour:02d}:00–{self.end_hour:02d}:59"


@dataclass(frozen=True)
class HealthMetric:
    """Definition of a health record type and how it should be aggregated."""

    record_type: str
    label: str
    aggregation: Literal["avg", "sum"] = "avg"
    morning_only: bool = False


ZEPP_SOURCE = "Zepp Life"
MORNING_WINDOW = MorningWindow()

ZEPP_METRICS: tuple[HealthMetric, ...] = (
    HealthMetric("HKQuantityTypeIdentifierBodyMass", "Body mass", morning_only=True),
    HealthMetric("HKQuantityTypeIdentifierBodyMassIndex", "BMI", morning_only=True),
    HealthMetric(
        "HKQuantityTypeIdentifierBodyFatPercentage",
        "Body fat %",
        morning_only=True,
    ),
    HealthMetric("HKQuantityTypeIdentifierLeanBodyMass", "Lean body mass", morning_only=True),
)

METRIC_BY_TYPE = {metric.record_type: metric for metric in ZEPP_METRICS}
BODY_MASS_METRIC = ZEPP_METRICS[0]
BODY_MASS_AXIS_FLOOR_KG = 53.0


@dataclass(frozen=True)
class ManualMetric:
    """Definition of a manually entered body measurement."""

    key: str
    label: str
    unit: str = "cm"


MANUAL_ENTRY_MEASUREMENTS: tuple[ManualMetric, ...] = (
    ManualMetric("neck", "Neck size"),
    ManualMetric("waist", "Waist size"),
    ManualMetric("hip", "Hip size"),
    ManualMetric("thigh", "Thigh size"),
    ManualMetric("arm", "Arm size"),
    ManualMetric("belly", "Belly size"),
    ManualMetric("weight", "Body mass", unit="kg"),
)

BODY_FAT_METRIC = ManualMetric("body_fat", "Body fat (US Army)", unit="%")

MANUAL_CHART_METRICS: tuple[ManualMetric, ...] = MANUAL_ENTRY_MEASUREMENTS + (BODY_FAT_METRIC,)

USER_HEIGHT_CM = 160.0

MANUAL_METRIC_BY_KEY = {metric.key: metric for metric in MANUAL_CHART_METRICS}
ENTERABLE_METRIC_KEYS = frozenset(metric.key for metric in MANUAL_ENTRY_MEASUREMENTS)

# Backward-compatible alias for entry-only lists.
MANUAL_BODY_MEASUREMENTS = MANUAL_ENTRY_MEASUREMENTS


@dataclass(frozen=True)
class NutritionMetric:
    """Definition of a dietary Apple Health record type."""

    record_type: str
    label: str
    unit: str
    min_daily_calories: float | None = None


MIN_DAILY_CALORIES = 1000.0
MIN_VALID_LOGGED_DAYS = 4

NUTRITION_METRICS: tuple[NutritionMetric, ...] = (
    NutritionMetric("HKQuantityTypeIdentifierDietaryCarbohydrates", "Carbohydrates", "g"),
    NutritionMetric("HKQuantityTypeIdentifierDietaryProtein", "Protein", "g"),
    NutritionMetric("HKQuantityTypeIdentifierDietaryFatTotal", "Total fat", "g"),
    NutritionMetric("HKQuantityTypeIdentifierDietaryFiber", "Fibre", "g"),
    NutritionMetric("HKQuantityTypeIdentifierDietarySodium", "Sodium", "mg"),
    NutritionMetric(
        "HKQuantityTypeIdentifierDietaryEnergyConsumed",
        "Calories",
        "kcal",
        min_daily_calories=MIN_DAILY_CALORIES,
    ),
)

NUTRITION_RECORD_TYPES = tuple(metric.record_type for metric in NUTRITION_METRICS)
NUTRITION_METRIC_BY_TYPE = {metric.record_type: metric for metric in NUTRITION_METRICS}
CALORIES_CONSUMED_METRIC = NUTRITION_METRIC_BY_TYPE[
    "HKQuantityTypeIdentifierDietaryEnergyConsumed"
]

POLAR_SOURCE = "Polar Flow"
GARMIN_SOURCE = "Garmin Connect"
FATSECRET_SOURCE = "FatSecret"
PREFERRED_ACTIVITY_SOURCES = (POLAR_SOURCE, GARMIN_SOURCE)

ACTIVITY_STEP_METRIC = HealthMetric(
    "HKQuantityTypeIdentifierStepCount",
    "Steps",
    aggregation="sum",
)

ACTIVE_ENERGY_METRIC = HealthMetric(
    "HKQuantityTypeIdentifierActiveEnergyBurned",
    "Calories spent",
    aggregation="sum",
)

WORKOUT_MEASURE_COUNT = "count"
WORKOUT_MEASURE_DURATION = "duration"
WORKOUT_MEASURES = (WORKOUT_MEASURE_COUNT, WORKOUT_MEASURE_DURATION)
