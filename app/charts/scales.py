"""Scale helpers for chart axes."""

import pandas as pd


def tight_y_domain(values: pd.Series, *, padding_ratio: float = 0.08) -> tuple[float, float]:
    """Build a y-axis range slightly wider than the data min and max.

    Args:
        values: Numeric series to bound the axis.
        padding_ratio: Fraction of the data range added above and below.

    Returns:
        Lower and upper axis limits.
    """
    clean = values.dropna()
    if clean.empty:
        return 0.0, 1.0

    min_value = float(clean.min())
    max_value = float(clean.max())
    if min_value == max_value:
        padding = max(abs(min_value) * padding_ratio, 0.5)
        return min_value - padding, max_value + padding

    padding = (max_value - min_value) * padding_ratio
    return min_value - padding, max_value + padding
