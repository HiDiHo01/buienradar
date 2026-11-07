"""Regression and informational benchmarks for JSON icon condition extraction."""

import json
from statistics import median
import timeit
from unittest.mock import patch

import pytest

import buienradar.buienradar_json as json_parser
from buienradar.constants import CONDCODE, CONDITION, DATA, FORECAST, IMAGE, NIGHTTIME, SUCCESS


_ICON_PREFIX = "https://www.buienradar.nl/resources/images/icons/weather/30x30/"
_BENCHMARK_REPEATS = 5


def _icon_url(suffix: str) -> str:
    """Create a deterministic weather icon URL for a given filename."""
    return f"{_ICON_PREFIX}{suffix}"


def _reference_condition(icon_url: object) -> dict[str, object] | None:
    """Implement the original full-string lowercase condition lookup."""
    if not isinstance(icon_url, str) or len(icon_url) < 6:
        return None

    image = icon_url.lower()
    code = image[-5:-4]
    night = image[-6:-5] == code
    cache = json_parser._COND_CACHE_NIGHT if night else json_parser._COND_CACHE_DAY
    condition = cache.get(code)
    return condition.copy() if condition is not None else None


def _weather_feed() -> str:
    """Build a stable local JSON feed with one station and five forecast days."""
    forecast_suffixes = ("a.png", "aa.png", "A.png", "aA.png", "b.png")
    forecast_days = [
        {
            "day": f"2026-11-{day:02d}T00:00:00",
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
            "iconurl": _icon_url(suffix),
        }
        for day, suffix in zip(range(11, 16), forecast_suffixes, strict=True)
    ]
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
                        "iconurl": _icon_url("Aa.png"),
                    }
                ]
            },
            "forecast": {"fivedayforecast": forecast_days},
        }
    )


@pytest.mark.parametrize(
    ("suffix", "expected_code", "expected_night"),
    [
        ("a.png", "a", False),
        ("A.png", "a", False),
        ("aa.png", "a", True),
        ("AA.png", "a", True),
        ("aA.png", "a", True),
        ("Aa.png", "a", True),
        ("b.png", "b", False),
        ("Bb.png", "b", True),
        ("x.png", None, None),
    ],
)
def test_icon_condition_cases(
    suffix: str, expected_code: str | None, expected_night: bool | None
) -> None:
    """Verify day/night detection, mixed-case suffixes, and unknown codes."""
    icon_url = _icon_url(suffix)
    condition = json_parser.__cond_from_image(icon_url)
    assert condition == _reference_condition(icon_url)

    if expected_code is None:
        assert condition is None
    else:
        assert condition is not None
        assert condition[CONDCODE] == expected_code
        assert condition[NIGHTTIME] is expected_night


@pytest.mark.parametrize(
    "invalid_icon",
    [None, 42, True, ["a.png"], {"url": "a.png"}, "", "a.png"],
)
def test_invalid_icon_condition_returns_none(invalid_icon: object) -> None:
    """Ignore invalid or too-short icon values without exceptions."""
    assert json_parser.__cond_from_image(invalid_icon) is None


def test_icon_condition_cache_returns_independent_dictionaries() -> None:
    """Avoid leaking mutations between results from cached condition templates."""
    first = json_parser.__cond_from_image(_icon_url("a.png"))
    second = json_parser.__cond_from_image(_icon_url("a.png"))
    assert first is not None
    assert second is not None
    assert first is not second

    first[CONDCODE] = "changed"
    assert second[CONDCODE] == "a"


def test_station_and_forecast_condition_paths() -> None:
    """Check complete weather parsing at both production call sites."""
    result = json_parser.parse_json_data(_weather_feed(), None, 52.09, 5.12)
    assert result[SUCCESS] is True
    weather = result[DATA]
    assert isinstance(weather, dict)

    station_condition = weather[CONDITION]
    assert isinstance(station_condition, dict)
    assert station_condition[CONDCODE] == "a"
    assert station_condition[NIGHTTIME] is True
    assert station_condition[IMAGE] == _icon_url("Aa.png")

    forecast = weather[FORECAST]
    assert len(forecast) == 5
    assert [day[CONDITION][CONDCODE] for day in forecast] == [
        "a", "a", "a", "a", "b"
    ]
    # Forecast icons are intentionally marked as daytime in the parser.
    assert all(day[CONDITION][NIGHTTIME] is False for day in forecast)


def _print_comparison(
    label: str, reference: list[float], candidate: list[float], batches: int
) -> None:
    """Show median times and ratios without an unstable performance gate."""
    reference_us = median(reference) * 1_000_000 / batches
    candidate_us = median(candidate) * 1_000_000 / batches
    assert reference_us > 0
    assert candidate_us > 0
    print(
        f"timeit {label}: main={reference_us:.3f} us, "
        f"candidate={candidate_us:.3f} us, "
        f"ratio={reference_us / candidate_us:.3f}x"
        f" ({batches} batches, {_BENCHMARK_REPEATS} repeats)"
    )


def test_timeit_icon_condition_helper() -> None:
    """Compare the old and new helper with equivalent output for all icon types."""
    icons = tuple(
        _icon_url(suffix)
        for suffix in ("a.png", "aa.png", "A.png", "AA.png", "aA.png", "b.png")
    )
    assert tuple(_reference_condition(icon) for icon in icons) == tuple(
        json_parser.__cond_from_image(icon) for icon in icons
    )

    def reference_batch() -> None:
        """Perform one baseline helper batch."""
        for icon in icons:
            _reference_condition(icon)

    def candidate_batch() -> None:
        """Perform one optimized helper batch."""
        for icon in icons:
            json_parser.__cond_from_image(icon)

    batches = 3_000
    reference = timeit.repeat(
        reference_batch, repeat=_BENCHMARK_REPEATS, number=batches
    )
    candidate = timeit.repeat(
        candidate_batch, repeat=_BENCHMARK_REPEATS, number=batches
    )
    _print_comparison("icon_helper", reference, candidate, batches)


def test_timeit_full_json_weather_parser() -> None:
    """Compare full feed parsing while substituting only the icon lookup helper."""
    payload = _weather_feed()

    def parse_feed() -> dict[str, object]:
        """Parse the same local JSON payload without network requests."""
        return json_parser.parse_json_data(payload, None, 52.09, 5.12)

    with patch.object(json_parser, "__cond_from_image", _reference_condition):
        baseline_result = parse_feed()
        baseline = timeit.repeat(parse_feed, repeat=_BENCHMARK_REPEATS, number=100)

    optimized_result = parse_feed()
    candidate = timeit.repeat(parse_feed, repeat=_BENCHMARK_REPEATS, number=100)

    assert baseline_result[SUCCESS] is True
    assert baseline_result == optimized_result
    _print_comparison("full_json_feed", baseline, candidate, 100)
