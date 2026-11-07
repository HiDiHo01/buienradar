"""Tests for JSON data parsing, wind helpers, and station validation."""
import pytest
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


def test_malformed_rain_payload_rows():
    """Test skipping malformed rows with extra or missing fields or non-numeric values."""
    from buienradar.buienradar_json import __parse_precipfc_data as parse_precip

    payload = "header\n077|12:00\n077|12:05|unexpected\ninvalid|12:10\n000|12:15\n"
    res = parse_precip(payload, 20)
    # Header skipped (index 0). Index 1 (077|12:00) valid. Index 2 (malformed field count) skipped.
    # Index 3 (non-numeric value) skipped. Index 4 (000|12:15) valid.
    # Total valid rows = 2
    assert res["average"] == 0.05
