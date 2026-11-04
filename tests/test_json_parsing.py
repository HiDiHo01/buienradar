"""Tests for JSON data parsing, wind helpers, and station validation."""
import json

import pytest

from buienradar.constants import CONDITION, DATA, MAX_RAIN, MIN_RAIN, RAIN, SUCCESS
from buienradar.buienradar_json import (
    __get_windspeed as get_windspeed,
    __get_windazimuth as get_windazimuth,
    __is_valid as is_valid,
    __parse_fc_data as parse_fc_data,
    parse_json_data,
)


def test_wind_helpers():
    """Test wind speed and azimuth lookups for valid and invalid inputs."""
    # Valid wind force Bft lookups
    assert get_windspeed(0) == 0.25
    assert get_windspeed(3) == 3.6
    assert get_windspeed(12) == 32.41
    # Invalid wind force
    assert get_windspeed(99) is None
    assert get_windspeed(None) is None
    assert get_windspeed("invalid") is None

    # Valid wind direction lookups
    assert get_windazimuth("N") == 0
    assert get_windazimuth("ZW") == 225
    assert get_windazimuth("zw") == 225
    assert get_windazimuth("OZO") == 112.5
    # Invalid wind direction
    assert get_windazimuth("") is None
    assert get_windazimuth(None) is None
    assert get_windazimuth("INVALID_DIR") is None


def test_is_valid_station():
    """Test station data validity check."""
    valid_station = {
        "airpressure": "1013.2",
        "temperature": "15.4",
        "humidity": "80",
    }
    assert is_valid(valid_station) is True

    none_station = {
        "airpressure": None,
        "temperature": None,
        "humidity": None,
    }
    assert is_valid(none_station) is None or is_valid(none_station) is False

    empty_station = {}
    assert is_valid(empty_station) is None or is_valid(empty_station) is False


def test_parse_fc_data():
    """Test parsing of 5-day forecast data."""
    fc_input = [
        {
            "day": "2023-05-11T00:00:00",
            "maxtemperatureMin": "18",
            "maxtemperatureMax": "20",
            "mintemperatureMin": "10",
            "mintemperatureMax": "12",
            "rainChance": "20",
            "sunChance": "60",
            "mmRainMin": "0",
            "mmRainMax": "1",
            "wind": "3",
            "windDirection": "zw",
            "iconurl": "https://www.buienradar.nl/resources/images/icons/weather/30x30/a.png",
        }
    ]

    parsed = parse_fc_data(fc_input)
    assert len(parsed) == 1
    day0 = parsed[0]
    assert day0["maxtemp"] == 20.0
    assert day0["mintemp"] == 10.0
    assert day0["temperature"] == 19.0
    assert day0["windforce"] == 3
    assert day0["windspeed"] == 3.6
    assert day0["winddirection"] == "ZW"
    assert day0["windazimuth"] == 225
    assert day0["condition"]["night"] is False


def test_full_parse_json_data():
    """Test complete parse_json_data workflow."""
    json_payload = """
    {
        "actual": {
            "stationmeasurements": [
                {
                    "stationid": 6260,
                    "stationname": "De Bilt",
                    "lat": "52.10",
                    "lon": "5.18",
                    "temperature": "15.4",
                    "airpressure": "1013.2"
                }
            ]
        },
        "forecast": {
            "fivedayforecast": [
                {
                    "day": "2023-05-11T00:00:00",
                    "maxtemperatureMin": "18",
                    "maxtemperatureMax": "20",
                    "mintemperatureMin": "10",
                    "mintemperatureMax": "12",
                    "rainChance": "20",
                    "sunChance": "60",
                    "mmRainMin": "0",
                    "mmRainMax": "1",
                    "wind": "3",
                    "windDirection": "zw",
                    "iconurl": "https://www.buienradar.nl/resources/images/icons/weather/30x30/a.png"
                }
            ]
        }
    }
    """
    rain_payload = "077|12:00\n000|12:05\n"

    res = parse_json_data(json_payload, rain_payload, 52.09, 5.12, 60)
    assert res["success"] is True
    assert res["data"]["temperature"] == 15.4
    assert res["data"]["stationname"] == "De Bilt (6260)"
    assert len(res["data"]["forecast"]) == 1


def test_condition_from_code():
    """Test condition lookup with string and integer codes."""
    from buienradar.buienradar import condition_from_code

    res_str = condition_from_code("a")
    assert res_str is not None
    assert res_str["condition"] == "clear"
    assert "exact_nl" in res_str

    res_int = condition_from_code(ord("a"))
    assert res_int is not None
    assert res_int["condition"] == "clear"
    assert res_int["condcode"] == ord("a")
    assert "exact_nl" in res_int

    res_str_upper = condition_from_code("A")
    assert res_str_upper is not None
    assert res_str_upper["condition"] == "clear"

    res_invalid = condition_from_code("nonexistent")
    assert res_invalid is None

    with pytest.raises(TypeError):
        condition_from_code(None)


@pytest.mark.parametrize(
    "invalid_icon", [None, 42, True, ["a.png"], {"url": "a.png"}]
)
def test_invalid_station_icon_is_ignored(invalid_icon: object) -> None:
    """Malformed station icon values must not abort valid weather parsing."""
    payload = {
        "actual": {
            "stationmeasurements": [
                {
                    "stationid": 6260,
                    "stationname": "De Bilt",
                    "lat": "52.10",
                    "lon": "5.18",
                    "temperature": "15.4",
                    "iconurl": invalid_icon,
                }
            ]
        },
        "forecast": {"fivedayforecast": []},
    }

    result = parse_json_data(json.dumps(payload), None, 52.09, 5.12)
    assert result[SUCCESS] is True
    assert result[DATA][CONDITION] is None
    assert result[DATA]["temperature"] == 15.4


@pytest.mark.parametrize(
    "invalid_icon", [None, 42, True, ["a.png"], {"url": "a.png"}]
)
def test_invalid_forecast_icon_is_ignored(invalid_icon: object) -> None:
    """Malformed forecast icon values must not abort forecast parsing."""
    result = parse_fc_data([{"iconurl": invalid_icon}])
    assert result[0][CONDITION] is None


@pytest.mark.parametrize("invalid_direction", [["ZW"], {"direction": "ZW"}, {"ZW"}])
def test_unhashable_wind_direction_returns_none(invalid_direction: object) -> None:
    """Return None for non-string, unhashable wind directions."""
    assert get_windazimuth(invalid_direction) is None


def test_unhashable_string_wind_direction_remains_supported() -> None:
    """Retain uppercase fallback support for unhashable string subclasses."""

    class UnhashableDirection(str):
        """String subclass whose instances cannot be dictionary keys."""

        __hash__ = None

    assert get_windazimuth(UnhashableDirection("zw")) == 225


@pytest.mark.parametrize(
    ("rain_values", "expected_rain", "expected_min", "expected_max"),
    [
        ({"mmRainMin": "1", "mmRainMax": "3"}, 2.0, 1.0, 3.0),
        ({"mmRainMin": "invalid", "mmRainMax": "3"}, 3.0, 0.0, 3.0),
        ({"mmRainMax": "3"}, 3.0, 0.0, 3.0),
        ({"mmRainMin": "1"}, 1.0, 1.0, 0.0),
        ({"mmRainMin": None, "mmRainMax": "invalid"}, None, 0.0, 0.0),
        ({}, None, 0.0, 0.0),
    ],
)
def test_forecast_rain_values_preserve_missing_value_semantics(
    rain_values: dict[str, object],
    expected_rain: float | None,
    expected_min: float,
    expected_max: float,
) -> None:
    """Reuse parsed rain values without changing invalid-field behavior."""
    result = parse_fc_data([rain_values])[0]
    assert result[RAIN] == expected_rain
    assert result[MIN_RAIN] == expected_min
    assert result[MAX_RAIN] == expected_max
