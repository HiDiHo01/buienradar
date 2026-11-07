"""Verify JSON/XML precipitation parsing and benchmark realistic callers."""

import json
import logging
from collections.abc import Callable
from statistics import median
import timeit
from types import ModuleType
from unittest.mock import patch

import pytest

import buienradar.buienradar_json as json_parser
import buienradar.buienradar_xml as xml_parser
from buienradar.constants import (
    AVERAGE,
    DATA,
    PRECIPITATION_FORECAST,
    SUCCESS,
    TIMEFRAME,
    TOTAL,
)


_BENCHMARK_REPEATS = 5
_PARSERS = (
    pytest.param(json_parser, id="json"),
    pytest.param(xml_parser, id="xml"),
)


def _reference_parser(
    module: ModuleType,
) -> Callable[[str, int], dict[str, float | int | None]]:
    """Build a baseline with the pre-optimization split and logging behavior."""
    logger = module.log
    mmu_lookup = module._MMU_LOOKUP

    def parse_precipitation(data: str, timeframe: int) -> dict[str, float | int | None]:
        """Parse precipitation rows as in main before the PR."""
        result = {AVERAGE: None, TOTAL: None, TIMEFRAME: None}
        logger.debug("Precipitation data: %s", data)
        lines = data.splitlines()
        total_rain = 0.0
        valid_lines = 0
        line_count = min(len(lines), round(float(timeframe) / 5) + 1)

        for index in range(1, line_count):
            line = lines[index]
            logger.debug("__parse_precipfc_data: line: %s", line)
            fields = line.split("|")
            if len(fields) != 2:
                logger.warning("Skipping malformed precipitation line: %r", line)
                continue

            value_text = fields[0]
            try:
                value_int = int(value_text)
                if 0 <= value_int <= 255:
                    intensity = mmu_lookup[value_int]
                else:
                    intensity = 10 ** ((value_int - 109) / 32)
            except ValueError:
                try:
                    value_float = float(value_text.replace(",", "."))
                    intensity = 10 ** ((value_float - 109) / 32)
                except ValueError:
                    logger.warning(
                        "Skipping invalid numeric precipitation value: %r", line
                    )
                    continue

            total_rain += intensity
            valid_lines += 1

        result[AVERAGE] = round(total_rain / valid_lines, 2) if valid_lines else 0
        result[TOTAL] = round(total_rain / 12, 2)
        result[TIMEFRAME] = timeframe
        return result

    return parse_precipitation


def _rain_payload() -> str:
    """Create a full 120-minute precipitation payload with 24 data rows."""
    values = (0, 77, 88, 109, 180, 255)
    rows = [
        f"{values[index % len(values)]:03d}|"
        f"{12 + index // 12:02d}:{index % 12 * 5:02d}"
        for index in range(24)
    ]
    return "header\n" + "\n".join(rows) + "\n"


def _json_weather_payload() -> str:
    """Build a complete, network-free JSON station and forecast response."""
    return json.dumps(
        {
            "actual": {
                "stationmeasurements": [
                    {
                        "stationid": 6260,
                        "stationname": "De Bilt",
                        "lat": "52.10",
                        "lon": "5.18",
                        "temperature": "15.4",
                        "airpressure": "1013.2",
                        "humidity": "80",
                        "iconurl": "https://example.invalid/a.png",
                    }
                ]
            },
            "forecast": {"fivedayforecast": []},
        }
    )


def _xml_weather_payload() -> str:
    """Provide the XML station shape exercised by existing parser tests."""
    return """
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
            <icoon ID="a">https://example.invalid/a.png</icoon>
            <maxtemp>20</maxtemp>
            <mintemp>10</mintemp>
          </dag-plus1>
        </verwachting_meerdaags>
      </weergegevens>
    </buienradarnl>
    """


@pytest.mark.parametrize("module", _PARSERS)
@pytest.mark.parametrize(
    ("payload", "timeframe"),
    [
        pytest.param("", 120, id="empty"),
        pytest.param("header\n", 120, id="header-only"),
        pytest.param("header\n077|12:00\n000|12:05\n", 120, id="two-valid-rows"),
        pytest.param(
            "header\n077|12:00|extra\n077|12:05\n", 120, id="extra-separator"
        ),
        pytest.param("header\n077\n077|12:05\n", 120, id="missing-separator"),
        pytest.param("header\n|12:00\ninvalid|12:05\n", 120, id="invalid-values"),
        pytest.param("header\n1,5|12:00\n255|12:05\n", 120, id="comma-decimal"),
        pytest.param("header\n256|12:00\n-1|12:05\n", 120, id="out-of-range"),
        pytest.param(_rain_payload(), 120, id="full-two-hours"),
        pytest.param(_rain_payload(), 5, id="first-five-minutes-only"),
        pytest.param(_rain_payload(), 60, id="twelve-rows-only"),
    ],
)
def test_precipitation_output_parity(
    module: ModuleType, payload: str, timeframe: int
) -> None:
    """Maintain original averages, totals and timeframe on both parsers."""
    reference = _reference_parser(module)
    expected = reference(payload, timeframe)
    actual = module.__parse_precipfc_data(payload, timeframe)
    assert actual == expected
    assert set(actual) == {AVERAGE, TOTAL, TIMEFRAME}
    assert actual[TIMEFRAME] == timeframe


@pytest.mark.parametrize("module", _PARSERS)
def test_precipitation_debug_logging(
    module: ModuleType, caplog: pytest.LogCaptureFixture
) -> None:
    """Retain per-line DEBUG diagnostics when the logger is enabled."""
    payload = "header\n077|12:00\n"
    with caplog.at_level(logging.DEBUG, logger=module.log.name):
        result = module.__parse_precipfc_data(payload, 5)
    assert result[AVERAGE] > 0
    assert any(
        "__parse_precipfc_data: line: 077|12:00" in record.message
        for record in caplog.records
    )


def _report_comparison(
    label: str, reference: list[float], candidate: list[float], repetitions: int
) -> None:
    """Print median microseconds and speedup without a timing assertion."""
    baseline_us = median(reference) * 1_000_000 / repetitions
    candidate_us = median(candidate) * 1_000_000 / repetitions
    assert baseline_us > 0
    assert candidate_us > 0
    print(
        f"timeit {label}: main={baseline_us:.3f} us, "
        f"candidate={candidate_us:.3f} us, "
        f"ratio={baseline_us / candidate_us:.3f}x"
    )


@pytest.mark.parametrize("module", _PARSERS)
def test_timeit_precipitation_helper(module: ModuleType) -> None:
    """Compare baseline and optimized 24-row precipitation helper processing."""
    payload = _rain_payload()
    baseline_parser = _reference_parser(module)
    candidate_parser = module.__parse_precipfc_data
    assert baseline_parser(payload, 120) == candidate_parser(payload, 120)

    repetitions = 800
    baseline = timeit.repeat(
        lambda: baseline_parser(payload, 120),
        number=repetitions,
        repeat=_BENCHMARK_REPEATS,
    )
    candidate = timeit.repeat(
        lambda: candidate_parser(payload, 120),
        number=repetitions,
        repeat=_BENCHMARK_REPEATS,
    )
    _report_comparison(f"{module.__name__}_helper", baseline, candidate, repetitions)


@pytest.mark.parametrize("module", _PARSERS)
def test_timeit_complete_weather_parser(module: ModuleType) -> None:
    """Compare real JSON/XML weather parsing with precipitation handler swapped."""
    rain_payload = _rain_payload()
    weather_payload = (
        _json_weather_payload()
        if module is json_parser
        else _xml_weather_payload()
    )

    def parse_weather() -> dict[str, object]:
        """Parse local weather and precipitation through the public function."""
        parse = (
            json_parser.parse_json_data
            if module is json_parser
            else xml_parser.parse_xml_data
        )
        return parse(weather_payload, rain_payload, 52.09, 5.12, 120)

    baseline_parser = _reference_parser(module)
    with patch.object(module, "__parse_precipfc_data", baseline_parser):
        expected = parse_weather()
        baseline = timeit.repeat(
            parse_weather, number=90, repeat=_BENCHMARK_REPEATS
        )

    actual = parse_weather()
    assert actual[SUCCESS] is True
    assert expected == actual
    assert actual[DATA][PRECIPITATION_FORECAST][TIMEFRAME] == 120
    candidate = timeit.repeat(
        parse_weather, number=90, repeat=_BENCHMARK_REPEATS
    )
    _report_comparison(f"{module.__name__}_full", baseline, candidate, 90)
