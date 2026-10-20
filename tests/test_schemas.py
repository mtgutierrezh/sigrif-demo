import pytest
from pydantic import ValidationError

from sigrif.schemas import ReadingIn


def test_valid_reading():
    reading = ReadingIn(
        zone_id=1,
        temperature=30.0,
        humidity=40.0,
        wind_speed=20.0,
        vegetation=0.6,
        slope=12.0,
    )
    assert reading.zone_id == 1


def test_invalid_humidity_is_rejected():
    with pytest.raises(ValidationError):
        ReadingIn(
            zone_id=1,
            temperature=30.0,
            humidity=140.0,
            wind_speed=20.0,
            vegetation=0.6,
            slope=12.0,
        )
