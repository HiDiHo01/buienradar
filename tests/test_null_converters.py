"""Verify and benchmark missing-value conversion in JSON and XML parsing."""

from statistics import median
from timeit import repeat
from types import ModuleType
from unittest.mock import patch

import pytest

import buienradar.buienradar_json as json_parser
import buienradar.buienradar_xml as xml_parser
from buienradar.constants import DATA, MESSAGE, SUCCESS


@pytest.mark.parametrize(
    "parser",
    [pytest.param(json_parser, id="json"), pytest.param(xml_parser, id="xml")],
)
@pytest.mark.parametrize(
    ("value", "expected"),
    [(None, 0), ("15", 15), ("invalid", 0), (False, 0), (True, 1)],
)
def test_int_conversion(
    parser: ModuleType, value: object, expected: int
) -> None:
    """Preserve integer conversion results and exact return types."""
    result = parser.__to_int(value)
    assert result == expected
    assert type(result) is int


@pytest.mark.parametrize(
    "parser",
    [pytest.param(json_parser, id="json"), pytest.param(xml_parser, id="xml")],
)
@pytest.mark.parametrize(
    ("value", "digits", "expected"),
    [
        (None, 1, 0.0),
        ("1.25", 1, 1.2),
        ("5.55", 2, 5.55),
        ("invalid", 2, 0.0),
        (False, 2, 0.0),
    ],
)
def test_float_conversion(
    parser: ModuleType, value: object, digits: int, expected: float
) -> None:
    """Preserve float rounding, fallback values and return types."""
    result = parser.__to_float(value, digits)
    assert result == expected
    assert type(result) is float


@pytest.mark.parametrize(
    ("value", "expected"),
    [(None, None), ("zw", "ZW"), ("NNO", "NNO"), (23, 23)],
)
def test_json_upper_conversion(value: object, expected: object) -> None:
    """Preserve uppercase handling and identity-compatible fallbacks."""
    assert json_parser.__to_upper(value) == expected


def _reference_int(value: object) -> int:
    """Convert integer values as the code did before the None fast path."""
    try:
        return int(value)
    except (AttributeError, ValueError, TypeError):
        return 0


def _reference_float(value: object, digits: int) -> float:
    """Convert float values as the code did before the None fast path."""
    try:
        return round(float(value), digits)
    except (AttributeError, ValueError, TypeError):
        return float(0)


def _reference_upper(value: object) -> object:
    """Convert uppercase values as the code did before the None fast path."""
    try:
        return value.upper()
    except (AttributeError, ValueError, TypeError):
        return value


def _result() -> dict[str, object]:
    """Initialize an independent result for a single station parse."""
    return {SUCCESS: False, MESSAGE: None, DATA: None}


def _station() -> dict[str, object]:
    """Create a reproducible station with missing and valid measurements."""
    return {
        "iconurl": "https://example.invalid/weather/a.png",
        "stationname": "Synthetic",
        "stationid": 6260,
        "humidity": None,
        "sunpower": "60",
        "temperature": None,
        "visibility": None,
        "winddirection": None,
        "windspeedBft": "3",
        "airpressure": "1013.2",
        "luchtvochtigheid": None,
        "temperatuurGC": None,
        "zichtmeters": None,
        "windsnelheidBF": "3",
        "luchtdruk": "1013.2",
    }


def _report(label: str, reference: list[float], candidate: list[float]) -> None:
    """Print informational median times without unstable speed assertions."""
    old_us = median(reference) * 1_000_000 / 150
    new_us = median(candidate) * 1_000_000 / 150
    assert old_us > 0
    assert new_us > 0
    print(
        f"timeit {label}: main={old_us:.3f} us, "
        f"candidate={new_us:.3f} us, ratio={old_us / new_us:.3f}x"
    )


def test_timeit_json_station_parser() -> None:
    """Compare actual JSON station parsing using reference and new converters."""
    station = _station()
    original = json_parser._REGULAR_SENSOR_ITEMS
    reference = tuple(
        (
            key,
            field,
            _reference_int if convert is json_parser.__to_int
            else _reference_upper if convert is json_parser.__to_upper
            else convert,
        )
        for key, field, convert in original
    )

    def parse() -> dict[str, object]:
        """Run the production JSON station parser."""
        return json_parser.__parse_loc_data(station, _result())

    with (
        patch.object(json_parser, "_REGULAR_SENSOR_ITEMS", reference),
        patch.object(json_parser, "__to_float", _reference_float),
    ):
        expected = parse()
        baseline_times = repeat(parse, repeat=3, number=150)

    actual = parse()
    candidate_times = repeat(parse, repeat=3, number=150)
    assert actual == expected
    _report("json_station", baseline_times, candidate_times)


def test_timeit_xml_station_parser() -> None:
    """Compare actual XML station parsing using reference and new converters."""
    station = _station()
    original = xml_parser.SENSOR_TYPES
    reference = {
        key: [field, _reference_int if convert is xml_parser.__to_int else convert]
        for key, (field, convert) in original.items()
    }

    def parse() -> dict[str, object]:
        """Run the production XML station parser."""
        return xml_parser.__parse_loc_data(station, _result())

    with (
        patch.object(xml_parser, "SENSOR_TYPES", reference),
        patch.object(xml_parser, "__to_float", _reference_float),
    ):
        expected = parse()
        baseline_times = repeat(parse, repeat=3, number=150)

    actual = parse()
    candidate_times = repeat(parse, repeat=3, number=150)
    assert actual == expected
    _report("xml_station", baseline_times, candidate_times)
