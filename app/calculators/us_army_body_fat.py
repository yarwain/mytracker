"""US Army body fat calculations."""

import math

CM_PER_INCH = 2.54


def us_army_body_fat_percent_female(
    neck_cm: float,
    waist_cm: float,
    hip_cm: float,
    height_cm: float,
) -> float:
    """Calculate body fat percentage using the US Army female formula.

    Measurements are stored in centimetres but converted to inches before applying:

    ``%BF = (163.205 * log10(waist + hip - neck)) - (97.684 * log10(height)) - 78.387``
    """
    neck_in = neck_cm / CM_PER_INCH
    waist_in = waist_cm / CM_PER_INCH
    hip_in = hip_cm / CM_PER_INCH
    height_in = height_cm / CM_PER_INCH

    circumference_sum = waist_in + hip_in - neck_in
    if circumference_sum <= 0 or height_in <= 0:
        msg = "Neck, waist, hip, and height must produce a valid body fat calculation."
        raise ValueError(msg)

    return (
        163.205 * math.log10(circumference_sum)
        - 97.684 * math.log10(height_in)
        - 78.387
    )
