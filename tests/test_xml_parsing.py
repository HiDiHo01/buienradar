"""Tests for XML timestamp parsing and forecast conditions."""

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from buienradar.buienradar import parse_data
from buienradar.buienradar_xml import __to_localdatetime as to_localdatetime

__ZI_TIMEZONE = ZoneInfo("Europe/Amsterdam")


@pytest.mark.parametrize(
    ("forecast_code", "expected_condition"),
    [
        pytest.param("a", "clear", id="known-condition"),
        pytest.param("x", None, id="unknown-condition"),
        pytest.param("", None, id="empty-condition"),
    ],
)
def test_parse_xml_forecast_conditions(
    forecast_code: str, expected_condition: str | None
) -> None:
    """Preserve XML measurements and later forecasts for unknown conditions."""
    xml_payload = f"""
    <buienradarnl>
      <weergegevens>
        <actueel_weer>
          <weerstations>
            <weerstation>
              <stationcode>6260</stationcode>
              <stationnaam regio="synthetic">Meetstation Synthetic</stationnaam>
              <lat>52.10</lat>
              <lon>5.18</lon>
              <luchtvochtigheid>80</luchtvochtigheid>
              <temperatuur10cm>13</temperatuur10cm>
              <zonintensiteitWM2>0</zonintensiteitWM2>
              <datum>10/24/2026 12:00:00</datum>
              <regenMMPU>0</regenMMPU>
              <luchtdruk>1013.2</luchtdruk>
              <icoonactueel ID="a">https://example.invalid/a.png</icoonactueel>
              <temperatuurGC>15.4</temperatuurGC>
              <zichtmeters>10000</zichtmeters>
              <windsnelheidMS>3</windsnelheidMS>
              <windsnelheidBF>2</windsnelheidBF>
              <windrichting>ZW</windrichting>
              <windrichtingGR>225</windrichtingGR>
              <windstotenMS>5</windstotenMS>
            </weerstation>
            <weerstation>
              <stationcode>6240</stationcode>
              <stationnaam regio="synthetic">Meetstation Secondary</stationnaam>
              <lat>52.32</lat>
              <lon>4.79</lon>
            </weerstation>
          </weerstations>
        </actueel_weer>
        <verwachting_meerdaags>
          <dag-plus1>
            <icoon ID="{forecast_code}">https://example.invalid/{forecast_code}.png</icoon>
            <maxtemp>20</maxtemp>
            <mintemp>10</mintemp>
          </dag-plus1>
          <dag-plus2>
            <icoon ID="b">https://example.invalid/b.png</icoon>
            <maxtemp>18</maxtemp>
            <mintemp>9</mintemp>
          </dag-plus2>
        </verwachting_meerdaags>
      </weergegevens>
    </buienradarnl>
    """

    parsed_weather = parse_data(xml_payload, None, 52.09, 5.12, api="xml")

    assert parsed_weather["success"] is True
    assert parsed_weather["msg"] is None
    weather_data = parsed_weather["data"]
    assert isinstance(weather_data, dict)
    assert weather_data["temperature"] == 15.4
    assert weather_data["stationname"] == "Synthetic (6260)"
    assert weather_data["condition"]["condcode"] == "a"

    forecast_entries = weather_data["forecast"]
    assert len(forecast_entries) == 2
    assert forecast_entries[0]["maxtemp"] == 20.0
    assert forecast_entries[0]["mintemp"] == 10.0

    forecast_condition = forecast_entries[0]["condition"]
    if expected_condition is None:
        assert forecast_condition is None
    else:
        assert forecast_condition is not None
        assert forecast_condition["condition"] == expected_condition
        assert forecast_condition["image"] == "https://example.invalid/a.png"
        assert "exact_nl" in forecast_condition

    assert forecast_entries[1]["maxtemp"] == 18.0
    assert forecast_entries[1]["condition"]["condcode"] == "b"
    assert forecast_entries[1]["condition"]["image"] == "https://example.invalid/b.png"


def test_xml_to_localdatetime() -> None:
    """Test XML timestamp parsing fast-path and fallbacks."""
    # Fast path standard MM/DD/YYYY HH:MM:SS format
    parsed_datetime = to_localdatetime("05/11/2023 12:30:45")
    expected_datetime = datetime(2023, 5, 11, 12, 30, 45, tzinfo=__ZI_TIMEZONE)
    assert parsed_datetime == expected_datetime

    # A valid single-digit month uses the strptime fallback.
    assert to_localdatetime("5/11/2023 12:30:45") == expected_datetime

    # Invalid digit range (e.g. month 99) triggers ValueError -> strptime fallback -> returns None
    assert to_localdatetime("99/11/2023 12:30:45") is None

    # Non-string or empty inputs
    assert to_localdatetime(None) is None
    assert to_localdatetime("") is None
    assert to_localdatetime("invalid") is None
