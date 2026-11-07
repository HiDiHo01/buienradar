"""Compare wind lookup changes with the main-branch behavior using timeit.

Correctness is mandatory; timing differences are diagnostic rather than CI gates.
"""

from collections.abc import Callable
from statistics import median
import timeit
from unittest.mock import patch

import buienradar.buienradar_json as json_parser


_TIMEIT_REPEATS = 5
_REFERENCE_WIND_DIRECTIONS: dict[str, float | int] = {
    direction: azimuth
    for direction, azimuth in json_parser._WIND_DIRECTIONS.items()
    if direction == direction.upper()
}


def _reference_wind_azimuth(direction: str | None) -> float | int | None:
    """Replicate the wind lookup on main before the lowercase alias change."""
    if not direction:
        return None

    if type(direction) is str:
        result = _REFERENCE_WIND_DIRECTIONS.get(direction)
        if result is not None:
            return result

    try:
        return _REFERENCE_WIND_DIRECTIONS.get(direction.upper())
    except (AttributeError, TypeError):
        return None


def _five_day_forecast() -> list[dict[str, str]]:
    """Build an unchanging, network-free five-day forecast workload."""
    directions = ("zw", "NO", "SSE", "wnw", "n")
    return [
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
            "windDirection": direction,
            "iconurl": "https://www.buienradar.nl/resources/images/icons/weather/30x30/a.png",
        }
        for day, direction in zip(range(11, 16), directions, strict=True)
    ]


def _report_timeit_comparison(
    label: str,
    reference_samples: list[float],
    candidate_samples: list[float],
    iterations: int,
    record_property: Callable[[str, object], None],
) -> None:
    """Record median timing and ratio without a flaky performance assertion."""
    reference_us = median(reference_samples) * 1_000_000 / iterations
    candidate_us = median(candidate_samples) * 1_000_000 / iterations

    assert reference_us > 0
    assert candidate_us > 0

    speedup = reference_us / candidate_us
    record_property(f"timeit_{label}_reference_us", round(reference_us, 6))
    record_property(f"timeit_{label}_candidate_us", round(candidate_us, 6))
    record_property(f"timeit_{label}_speedup", round(speedup, 4))

    print(
        f"timeit {label}: reference={reference_us:.3f} us, "
        f"candidate={candidate_us:.3f} us, ratio={speedup:.3f}x "
        f"({iterations} batches, {_TIMEIT_REPEATS} repeats)"
    )


def test_timeit_direct_wind_lookup(
    record_property: Callable[[str, object], None],
) -> None:
    """Compare identical direct helper inputs and verify equal results."""
    directions = ("n", "no", "zw", "sse", "nnw", "ENE", "Zw", "invalid")
    assert tuple(_reference_wind_azimuth(item) for item in directions) == tuple(
        json_parser.__get_windazimuth(item) for item in directions
    )

    def run_reference() -> None:
        """Execute one batch of the main-branch lookup."""
        for direction in directions:
            _reference_wind_azimuth(direction)

    def run_candidate() -> None:
        """Execute one batch of the PR lookup."""
        for direction in directions:
            json_parser.__get_windazimuth(direction)

    iterations = 3_000
    reference = timeit.repeat(
        run_reference, repeat=_TIMEIT_REPEATS, number=iterations
    )
    candidate = timeit.repeat(
        run_candidate, repeat=_TIMEIT_REPEATS, number=iterations
    )
    _report_timeit_comparison(
        "direct_lookup", reference, candidate, iterations, record_property
    )


def test_timeit_five_day_forecast(
    record_property: Callable[[str, object], None],
) -> None:
    """Compare real forecast parsing with only the wind lookup substituted."""
    forecast = _five_day_forecast()
    optimized_lookup = json_parser.__get_windazimuth

    with patch.object(json_parser, "__get_windazimuth", _reference_wind_azimuth):
        reference_result = json_parser.__parse_fc_data(forecast)
        reference = timeit.repeat(
            lambda: json_parser.__parse_fc_data(forecast),
            repeat=_TIMEIT_REPEATS,
            number=250,
        )

    with patch.object(json_parser, "__get_windazimuth", optimized_lookup):
        candidate_result = json_parser.__parse_fc_data(forecast)
        candidate = timeit.repeat(
            lambda: json_parser.__parse_fc_data(forecast),
            repeat=_TIMEIT_REPEATS,
            number=250,
        )

    assert reference_result == candidate_result
    assert len(reference_result) == 5
    _report_timeit_comparison(
        "five_day_forecast", reference, candidate, 250, record_property
    )
