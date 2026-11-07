"""Validate XML station fast paths with deterministic regression and timeit tests."""

from collections.abc import Callable
from statistics import median
import timeit
from unittest.mock import Mock, patch

import pytest

import buienradar.buienradar_xml as xml_parser
from buienradar.constants import (
    CONDITION,
    DATA,
    HUMIDITY,
    MEASURED,
    STATIONNAME,
    SUCCESS,
    TEMPERATURE,
)


_TIMEIT_REPEATS = 5


def _reference_is_valid(station_data: dict[str, object]) -> bool | None:
    """Replicate main's converter-based validation without a station-level guard."""
    for key, (attribute, converter) in xml_parser.SENSOR_TYPES.items():
        if key not in (CONDITION, STATIONNAME, MEASURED) and converter is not None:
            if converter(station_data.get(attribute)) != 0:
                return True
    return None


def _station_values(complete: bool) -> dict[str, object]:
    """Create a sparse or complete station using the published sensor fields."""
    values: dict[str, object] = {"temperatuurGC": "15.4"}
    if complete:
        values.update(
            {
                "luchtvochtigheid": "80",
                "temperatuur10cm": "13",
                "zonintensiteitWM2": "0",
                "regenMMPU": "0",
                "luchtdruk": "1013.2",
                "zichtmeters": "10000",
                "windsnelheidMS": "3",
                "windsnelheidBF": "2",
                "windrichtingGR": "225",
                "windstotenMS": "5",
            }
        )
    return values


def _xml_weather_feed(complete: bool) -> str:
    """Build a deterministic two-station XML feed for real parser timing."""
    sensor_fields = "".join(
        f"<{field}>{value}</{field}>"
        for field, value in _station_values(complete).items()
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
              <datum>10/24/2026 12:00:00</datum>
              <icoonactueel ID="a">https://example.invalid/a.png</icoonactueel>
              <windrichting>ZW</windrichting>
              {sensor_fields}
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


@pytest.mark.parametrize(
    ("station_data", "expected"),
    [
        pytest.param({}, None, id="missing-all"),
        pytest.param(
            {"luchtvochtigheid": None, "temperatuurGC": None},
            None,
            id="explicit-none",
        ),
        pytest.param(
            {"luchtvochtigheid": "0", "temperatuurGC": "0.0"},
            None,
            id="all-zero",
        ),
        pytest.param(
            {"luchtvochtigheid": "invalid", "temperatuurGC": "bad"},
            None,
            id="malformed-numeric",
        ),
        pytest.param(
            {"stationnaam": {"#text": "Synthetic"}, "windrichting": "ZW"},
            None,
            id="metadata-only",
        ),
        pytest.param({"luchtvochtigheid": "80"}, True, id="first-valid"),
        pytest.param({"temperatuurGC": "15.4"}, True, id="later-valid"),
        pytest.param({"windstotenMS": "2.5"}, True, id="last-valid"),
        pytest.param({"temperatuurGC": "-0.1"}, True, id="negative-nonzero"),
    ],
)
def test_xml_validation_matches_main(
    station_data: dict[str, object], expected: bool | None
) -> None:
    """Keep exact station validity and return types for all edge cases."""
    reference = _reference_is_valid(station_data)
    candidate = xml_parser.__is_valid(station_data)
    assert reference is expected
    assert candidate is expected


def test_xml_validation_skips_none_converter_calls() -> None:
    """Do not call field converters when the source value is absent or None."""
    converter = Mock(return_value=0)
    mapping = {HUMIDITY: ["luchtvochtigheid", converter]}
    with patch.object(xml_parser, "SENSOR_TYPES", mapping):
        assert xml_parser.__is_valid({}) is None
        assert xml_parser.__is_valid({"luchtvochtigheid": None}) is None
        converter.assert_not_called()
        assert xml_parser.__is_valid({"luchtvochtigheid": "0"}) is None
        converter.assert_called_once_with("0")


@pytest.mark.parametrize("complete", [False, True], ids=["sparse", "complete"])
def test_xml_full_parser_preserves_sensor_results(complete: bool) -> None:
    """Exercise actual station selection and XML validation before parsing."""
    content = _xml_weather_feed(complete)
    with patch.object(xml_parser, "__is_valid", _reference_is_valid):
        baseline = xml_parser.parse_xml_data(content, None, 52.09, 5.12)
    candidate = xml_parser.parse_xml_data(content, None, 52.09, 5.12)
    assert baseline == candidate
    assert candidate[SUCCESS] is True
    assert candidate[DATA][TEMPERATURE] == 15.4


def _report_timings(
    label: str, reference: list[float], candidate: list[float], batch_size: int
) -> None:
    """Print median microsecond timings; never require a speed threshold."""
    reference_us = median(reference) * 1_000_000 / batch_size
    candidate_us = median(candidate) * 1_000_000 / batch_size
    assert reference_us > 0
    assert candidate_us > 0
    print(
        f"timeit {label}: main={reference_us:.3f} us, "
        f"candidate={candidate_us:.3f} us, "
        f"ratio={reference_us / candidate_us:.3f}x"
    )


@pytest.mark.parametrize("complete", [False, True], ids=["sparse", "complete"])
def test_timeit_xml_validation_helper(complete: bool) -> None:
    """Compare current-main validation with the new early-None guard."""
    station = _station_values(complete)
    assert _reference_is_valid(station) is xml_parser.__is_valid(station)

    batches = 5_000
    reference = timeit.repeat(
        lambda: _reference_is_valid(station),
        repeat=_TIMEIT_REPEATS,
        number=batches,
    )
    candidate = timeit.repeat(
        lambda: xml_parser.__is_valid(station),
        repeat=_TIMEIT_REPEATS,
        number=batches,
    )
    _report_timings(
        f"xml_validation_{'complete' if complete else 'sparse'}",
        reference,
        candidate,
        batches,
    )


@pytest.mark.parametrize("complete", [False, True], ids=["sparse", "complete"])
def test_timeit_full_xml_weather_parser(complete: bool) -> None:
    """Compare full weather parsing by swapping only the validity check."""
    content = _xml_weather_feed(complete)

    def parse_weather() -> dict[str, object]:
        """Parse a complete XML payload with no external requests."""
        return xml_parser.parse_xml_data(content, None, 52.09, 5.12)

    with patch.object(xml_parser, "__is_valid", _reference_is_valid):
        baseline = parse_weather()
        reference_times = timeit.repeat(
            parse_weather, repeat=_TIMEIT_REPEATS, number=100
        )
    candidate = parse_weather()
    assert baseline == candidate
    assert candidate[SUCCESS] is True
    candidate_times = timeit.repeat(
        parse_weather, repeat=_TIMEIT_REPEATS, number=100
    )
    _report_timings(
        f"full_xml_{'complete' if complete else 'sparse'}",
        reference_times,
        candidate_times,
        100,
    )


def _current_main_live_xml_validator(station_data: dict[str, object]) -> bool | None:
    """Model the base commit's live SENSOR_TYPES and None-guard behavior."""
    for key, (attribute, converter) in xml_parser.SENSOR_TYPES.items():
        if key not in (CONDITION, STATIONNAME, MEASURED) and converter is not None:
            value = station_data.get(attribute)
            if value is not None and converter(value) != 0:
                return True
    return None


def test_xml_validation_tracks_added_changed_removed_sensor_fields() -> None:
    """Keep station validation synchronized with dynamically edited descriptors."""
    mapping = {HUMIDITY: ["luchtvochtigheid", xml_parser.__to_int]}
    with patch.object(xml_parser, "SENSOR_TYPES", mapping):
        assert xml_parser.__is_valid({}) is None
        assert xml_parser.__is_valid({"custom": "17"}) is None

        mapping["synthetic_sensor"] = ["custom", int]
        assert xml_parser.__is_valid({"custom": "17"}) is True

        mapping["synthetic_sensor"][0] = "replacement"
        assert xml_parser.__is_valid({"custom": "17"}) is None
        assert xml_parser.__is_valid({"replacement": "17"}) is True

        mapping["synthetic_sensor"][1] = lambda value: 0
        assert xml_parser.__is_valid({"replacement": "17"}) is None

        mapping["synthetic_sensor"][1] = int
        del mapping["synthetic_sensor"]
        assert xml_parser.__is_valid({"replacement": "17"}) is None


def test_xml_full_parser_accepts_updated_sensor_schema() -> None:
    """Accept a weather station whose only nonzero value uses a changed field."""
    feed = _xml_weather_feed(False).replace(
        "<temperatuurGC>15.4</temperatuurGC>",
        "<maatwerk>15.4</maatwerk>",
    )
    modified_mapping = {
        TEMPERATURE: ["maatwerk", xml_parser.__to_float1],
    }
    with patch.object(xml_parser, "SENSOR_TYPES", modified_mapping):
        baseline = xml_parser.parse_xml_data(feed, None, 52.09, 5.12)
        assert baseline[SUCCESS] is True
        assert baseline[DATA][TEMPERATURE] == 15.4
        assert xml_parser.__is_valid({"maatwerk": "15.4"}) is True


@pytest.mark.parametrize("complete", [False, True], ids=["sparse", "complete"])
def test_timeit_live_xml_schema_helper(complete: bool) -> None:
    """Benchmark current-main validation and the live optimized predicate."""
    values = _station_values(complete)
    baseline = _current_main_live_xml_validator
    candidate = xml_parser.__is_valid
    assert baseline(values) is candidate(values)

    samples = timeit.repeat(
        lambda: baseline(values), repeat=_TIMEIT_REPEATS, number=5_000
    )
    measurements = timeit.repeat(
        lambda: candidate(values), repeat=_TIMEIT_REPEATS, number=5_000
    )
    _report_timings(
        f"live_schema_helper_{'complete' if complete else 'sparse'}",
        samples,
        measurements,
        5_000,
    )


@pytest.mark.parametrize("complete", [False, True], ids=["sparse", "complete"])
def test_timeit_live_xml_schema_full_parser(complete: bool) -> None:
    """Compare complete XML parsing against the actual live-mapping baseline."""
    feed = _xml_weather_feed(complete)

    def parse_weather() -> dict[str, object]:
        """Parse an identical two-station XML fixture without network access."""
        return xml_parser.parse_xml_data(feed, None, 52.09, 5.12)

    with patch.object(xml_parser, "__is_valid", _current_main_live_xml_validator):
        baseline = parse_weather()
        sample_times = timeit.repeat(
            parse_weather, repeat=_TIMEIT_REPEATS, number=100
        )

    result = parse_weather()
    assert baseline == result
    assert result[SUCCESS] is True

    candidate_times = timeit.repeat(
        parse_weather, repeat=_TIMEIT_REPEATS, number=100
    )
    _report_timings(
        f"live_schema_full_{'complete' if complete else 'sparse'}",
        sample_times,
        candidate_times,
        100,
    )
