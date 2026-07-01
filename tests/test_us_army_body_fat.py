import pytest

from app.calculators.us_army_body_fat import us_army_body_fat_percent_female
from app.config import USER_HEIGHT_CM


def test_us_army_body_fat_female_example() -> None:
    body_fat = us_army_body_fat_percent_female(
        neck_cm=31.0,
        waist_cm=69.0,
        hip_cm=96.0,
        height_cm=USER_HEIGHT_CM,
    )
    assert body_fat == pytest.approx(26.93, abs=0.01)


def test_us_army_body_fat_rejects_invalid_circumference() -> None:
    with pytest.raises(ValueError, match="valid body fat"):
        us_army_body_fat_percent_female(
            neck_cm=200.0,
            waist_cm=69.0,
            hip_cm=96.0,
            height_cm=USER_HEIGHT_CM,
        )
