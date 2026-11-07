"""Exercise safe XML forecast optimizations and record real parsing timings."""

from datetime import datetime, timedelta
from statistics import median
import timeit
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pytest

import buienradar.buienradar_xml as xml_parser
from buienradar.buienradar import condition_from_code
from buienradar.constants import (
    CONDITION,
    DATA,
    DATETIME,
    FORECAST,
    IMAGE,
    MAX_TEMP,
    MIN_TEMP,
    RAIN,
    RAIN_CHANCE,
    SNOW,
    SUCCESS,
    SUN_CHANCE,
    TEMPERATURE,
    WINDFORCE,
)


_REPEAT_COUNT = 5


def _forecast_data() -> dict[str, dict[str, object]]:
    """Create all five days, including unknown codes and bad numeric fields."""
    days: dict[str, dict[str, object]] = {}
    for day_index in range(1, 6):
        code = "x" if day_index == 5 else ("a" if day_index % 2 else "b")
        days[f"dag-plus{day_index}"] = {
            "icoon": {"@ID": code, "#text": f"https://example.invalid/{code}.png"},
            "maxtemp": str(18 + day_index),
            "mintemp": str(8 + day_index),
            "kanszon": "60",
            "kansregen": "20",
            "maxmmregen": "1.5",
            "sneeuwcms": "0",
            "windkracht": "3",
        }
    days["dag-plus3"]["maxtemp"] = "invalid"
    del days["dag-plus4"]["mintemp"]
    return days


def _reference_forecast(forecast_data: dict[str, dict[str, object]]) -> list[dict[str, object]]:
    """Recreate current main's five-day parser with duplicate max-temp parsing."""
    result: list[dict[str, object]] = []
    base_date = datetime.now(ZoneInfo("Europe/Amsterdam")).replace(
        hour=12, minute=0, second=0, microsecond=0
    )
    for day_index in range(1, 6):
        section_key = "dag-plus%d" % day_index
        if section_key in forecast_data:
            section = forecast_data[section_key]
            forecast_date = base_date + timedelta(days=day_index)
            icon_code = section.get("icoon", []).get("@ID").lower()
            entry = {
                CONDITION: condition_from_code(icon_code),
                TEMPERATURE: xml_parser.__get_float(section, "maxtemp"),
                MIN_TEMP: xml_parser.__get_float(section, "mintemp"),
                MAX_TEMP: xml_parser.__get_float(section, "maxtemp"),
                SUN_CHANCE: xml_parser.__get_int(section, "kanszon"),
                RAIN_CHANCE: xml_parser.__get_int(section, "kansregen"),
                RAIN: xml_parser.__get_float(section, "maxmmregen"),
                SNOW: xml_parser.__get_float(section, "sneeuwcms"),
                WINDFORCE: xml_parser.__get_int(section, "windkracht"),
                DATETIME: forecast_date,
            }
            if entry[CONDITION] is not None:
                entry[CONDITION][IMAGE] = section.get("icoon", []).get("#text")
            result.append(entry)
    return result


def _xml_weather_payload(days: tuple[int, ...]) -> str:
    """Create a complete network-free XML feed with two valid weather stations."""
    records = _forecast_data()
    forecast = "".join(
        (
            f"<dag-plus{day_index}>"
            f'<icoon ID="{records[f"dag-plus{day_index}"]["icoon"]["@ID"]}">'
            f'{records[f"dag-plus{day_index}"]["icoon"]["#text"]}</icoon>'
            f'<maxtemp>{records[f"dag-plus{day_index}"]["maxtemp"]}</maxtemp>'
            + (
                f'<mintemp>{records[f"dag-plus{day_index}"]["mintemp"]}</mintemp>'
                if "mintemp" in records[f"dag-plus{day_index}"]
                else ""
            )
            + "<kanszon>60</kanszon><kansregen>20</kansregen>"
            "<maxmmregen>1.5</maxmmregen><sneeuwcms>0</sneeuwcms>"
            "<windkracht>3</windkracht>"
            f"</dag-plus{day_index}>"
        )
        for day_index in days
    )
    return f"""
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
              <temperatuurGC>15.4</temperatuurGC>
              <datum>10/24/2026 12:00:00</datum>
              <icoonactueel ID="a">https://example.invalid/a.png</icoonactueel>
            </weerstation>
            <weerstation>
              <stationcode>6240</stationcode>
              <stationnaam regio="synthetic">Meetstation Secondary</stationnaam>
              <lat>52.32</lat>
              <lon>4.79</lon>
            </weerstation>
          </weerstations>
        </actueel_weer>
        <verwachting_meerdaags>{forecast}</verwachting_meerdaags>
      </weergegevens>
    </buienradarnl>
    """


@pytest.mark.parametrize(
    "days",
    [
        pytest.param((1, 2, 3, 4, 5), id="all-five-days"),
        pytest.param((1, 3, 5), id="missing-days"),
        pytest.param((5,), id="last-day-only"),
        pytest.param((), id="no-days"),
    ],
)
def test_xml_forecast_matches_main(days: tuple[int, ...]) -> None:
    """Preserve all values, dates and condition codes for each forecast day."""
    source = _forecast_data()
    selected = {f"dag-plus{index}": source[f"dag-plus{index}"] for index in days}
    expected = _reference_forecast(selected)
    actual = xml_parser.__parse_fc_data(selected)
    assert actual == expected
    assert len(actual) == len(days)
    for entry in actual:
        assert entry[TEMPERATURE] == entry[MAX_TEMP]
        assert entry[DATETIME].tzinfo is not None


def test_xml_forecast_all_five_days_and_invalid_fields() -> None:
    """Cover all five slots, missing temperatures and unknown weather codes."""
    parsed = xml_parser.__parse_fc_data(_forecast_data())
    assert len(parsed) == 5
    assert parsed[0][TEMPERATURE] == 19.0
    assert parsed[2][TEMPERATURE] == 0.0
    assert parsed[3][MIN_TEMP] == 0.0
    assert parsed[4][CONDITION] is None
    assert parsed[0][CONDITION][IMAGE] == "https://example.invalid/a.png"


@pytest.mark.parametrize(
    "days",
    [
        pytest.param((1, 2), id="two-day"),
        pytest.param((1, 2, 3, 4, 5), id="five-day"),
    ],
)
def test_xml_full_weather_matches_main(days: tuple[int, ...]) -> None:
    """Verify production XML parsing matches before and after optimization."""
    weather = _xml_weather_payload(days)
    with patch.object(xml_parser, "__parse_fc_data", _reference_forecast):
        expected = xml_parser.parse_xml_data(weather, None, 52.09, 5.12)
    actual = xml_parser.parse_xml_data(weather, None, 52.09, 5.12)
    assert actual == expected
    assert actual[SUCCESS] is True
    assert len(actual[DATA][FORECAST]) == len(days)


def test_xml_sensor_mapping_remains_live() -> None:
    """Do not detach station parsing from an updated SENSOR_TYPES mapping."""
    weather = _xml_weather_payload((1, 2))
    mapping = {TEMPERATURE: ["temperatuurGC", xml_parser.__to_float1]}
    with patch.object(xml_parser, "SENSOR_TYPES", mapping):
        first = xml_parser.parse_xml_data(weather, None, 52.09, 5.12)
        assert first[SUCCESS] is True
        assert first[DATA][TEMPERATURE] == 15.4
        mapping["custom_sensor"] = ["luchtvochtigheid", int]
        second = xml_parser.parse_xml_data(weather, None, 52.09, 5.12)
        assert second[SUCCESS] is True
        assert second[DATA]["custom_sensor"] == 80
        mapping["custom_sensor"] = ["temperatuurGC", float]
        third = xml_parser.parse_xml_data(weather, None, 52.09, 5.12)
        assert third[DATA]["custom_sensor"] == 15.4
        del mapping["custom_sensor"]
        fourth = xml_parser.parse_xml_data(weather, None, 52.09, 5.12)
        assert "custom_sensor" not in fourth[DATA]


def _show_timing(
    label: str, baseline: list[float], candidate: list[float], repeats: int
) -> None:
    """Print median durations without gating the CI on performance."""
    old_us = median(baseline) * 1_000_000 / repeats
    new_us = median(candidate) * 1_000_000 / repeats
    assert old_us > 0
    assert new_us > 0
    print(f"timeit {label}: main={old_us:.3f} us, candidate={new_us:.3f} us, ratio={old_us/new_us:.3f}x")


@pytest.mark.parametrize("day_count", [2, 5])
def test_timeit_xml_forecast_helper(day_count: int) -> None:
    """Measure forecast helper on fixed two- and five-day test inputs."""
    source = _forecast_data()
    selected = {f"dag-plus{index}": source[f"dag-plus{index}"] for index in range(1, day_count + 1)}
    assert _reference_forecast(selected) == xml_parser.__parse_fc_data(selected)
    baseline = timeit.repeat(
        lambda: _reference_forecast(selected), repeat=_REPEAT_COUNT, number=1_000
    )
    candidate = timeit.repeat(
        lambda: xml_parser.__parse_fc_data(selected), repeat=_REPEAT_COUNT, number=1_000
    )
    _show_timing(f"xml_fc_helper_{day_count}", baseline, candidate, 1_000)


@pytest.mark.parametrize("day_count", [2, 5])
def test_timeit_xml_forecast_full_parser(day_count: int) -> None:
    """Benchmark the real XML parser with baseline/candidate forecast helpers."""
    weather = _xml_weather_payload(tuple(range(1, day_count + 1)))

    def parse_weather() -> dict[str, object]:
        """Parse a deterministic XML feed using the current forecast helper."""
        return xml_parser.parse_xml_data(weather, None, 52.09, 5.12)

    with patch.object(xml_parser, "__parse_fc_data", _reference_forecast):
        expected = parse_weather()
        baseline = timeit.repeat(parse_weather, repeat=_REPEAT_COUNT, number=100)

    actual = parse_weather()
    assert actual == expected
    assert actual[SUCCESS] is True
    candidate = timeit.repeat(parse_weather, repeat=_REPEAT_COUNT, number=100)
    _show_timing(f"xml_fc_full_{day_count}", baseline, candidate, 100)
