import pytest
from pydantic import ValidationError

from sigrif.schemas import ReadingIn, RiskFeaturesIn


def test_valid_reading():
    reading = ReadingIn(
        zone_id=1,
        temperature=30.0,
        humidity=40.0,
        wind_speed=20.0,
        vegetation=0.6,
        historical_fires=4,
        slope=12.0,
    )
    assert reading.zone_id == 1
    assert reading.historical_fires == 4


def test_invalid_humidity_is_rejected():
    with pytest.raises(ValidationError):
        ReadingIn(
            zone_id=1,
            temperature=30.0,
            humidity=140.0,
            wind_speed=20.0,
            vegetation=0.6,
            historical_fires=4,
            slope=12.0,
        )


def test_historical_fires_must_be_non_negative():
    with pytest.raises(ValidationError):
        RiskFeaturesIn(
            temperature=30.0,
            humidity=40.0,
            wind_speed=20.0,
            vegetation=0.6,
            historical_fires=-1,
            slope=12.0,
        )
