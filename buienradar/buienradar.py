"""
Buienradar library to retrieve and parse weather data from buienradar.nl.
"""
from __future__ import annotations

import logging
from typing import Literal, TypedDict

from buienradar.buienradar_json import get_json_data, parse_json_data
from buienradar.buienradar_xml import get_xml_data, parse_xml_data
from buienradar.constants import (
    __BRCONDITIONS,
    CONDCODE,
    CONDITION,
    DETAILED,
    EXACT,
    EXACTNL,
)

__all__ = (
    "get_data",
    "parse_data",
    "condition_from_code",
)

log = logging.getLogger(__name__)

_DEFAULT_LATITUDE: float = 52.091579
_DEFAULT_LONGITUDE: float = 5.119734
_DEFAULT_TIMEFRAME: int = 60


class ConditionData(TypedDict):
    """Structured representation of condition metadata."""

    condcode: int | str
    condition: str
    detailed: str
    exact: str
    exact_nl: str


# Precomputed condition data templates for fast O(1) lookups
_CONDITION_DATA_CACHE: dict[str, ConditionData] = {
    str(code).lower(): ConditionData(
        condcode=code,
        condition=val[0],
        detailed=val[1],
        exact=val[2],
        exact_nl=val[3],
    )
    for code, val in __BRCONDITIONS.items()
    if isinstance(val, (list, tuple)) and len(val) >= 4
}


def _validate_coordinates(latitude: float, longitude: float) -> None:
    """Validate geographic coordinates."""
    if not isinstance(latitude, (int, float)):
        raise TypeError("Latitude must be numeric")

    if not isinstance(longitude, (int, float)):
        raise TypeError("Longitude must be numeric")

    if not -90.0 <= float(latitude) <= 90.0:
        raise ValueError("Latitude must be between -90 and 90 degrees")

    if not -180.0 <= float(longitude) <= 180.0:
        raise ValueError("Longitude must be between -180 and 180 degrees")


def _validate_timeframe(timeframe: int) -> None:
    """Validate timeframe in minutes."""
    if not isinstance(timeframe, int):
        raise TypeError("Timeframe must be an integer")

    if not 5 <= timeframe <= 120:
        raise ValueError("Timeframe must be between 5 and 120 minutes")


def get_data(
    latitude: float = _DEFAULT_LATITUDE,
    longitude: float = _DEFAULT_LONGITUDE,
    *,
    api: Literal["json", "xml"] = "json",
) -> dict[str, object]:
    """
    Retrieve raw Buienradar weather data.

    Args:
        latitude: Geographic latitude.
        longitude: Geographic longitude.
        api: API format to use ("json" or "xml").

    Returns:
        Raw API response dictionary.
    """
    _validate_coordinates(latitude, longitude)

    log.info(
        "Getting buienradar %s data for latitude=%s, longitude=%s",
        api.upper(),
        latitude,
        longitude,
    )

    if api == "xml":
        return get_xml_data(latitude, longitude)

    return get_json_data(latitude, longitude)


def parse_data(
    content: object,
    raincontent: object,
    latitude: float = _DEFAULT_LATITUDE,
    longitude: float = _DEFAULT_LONGITUDE,
    timeframe: int = _DEFAULT_TIMEFRAME,
    usexml: bool | None = None,
    *,
    api: Literal["json","xml"] | None = None
) -> dict[str, object]:
    """
    Parse raw Buienradar data into structured dictionary.

    Args:
        content: Weather content.
        raincontent: Rain forecast content.
        latitude: Geographic latitude.
        longitude: Geographic longitude.
        timeframe: Minutes to look ahead.
        api: API format used ("json" or "xml").

    Returns:
        Parsed weather data dictionary.
    """
    _validate_coordinates(latitude, longitude)
    _validate_timeframe(timeframe)

    # --- normalize API selection ---
    if api is None:
        api = "xml" if usexml else "json"

    if api == "xml":
        return parse_xml_data(
            content,
            raincontent,
            latitude,
            longitude,
            timeframe,
        )

    return parse_json_data(
        content,
        raincontent,
        latitude,
        longitude,
        timeframe,
    )


def condition_from_code(condcode: int | str) -> ConditionData | None:
    """
    Retrieve condition metadata from a Buienradar condition code.

    Args:
        condcode: Numeric or string condition code.

    Returns:
        ConditionData dictionary if known, otherwise None.
    """
    if not isinstance(condcode, (int, str)):
        raise TypeError("Condition code must be an integer or string")

    if isinstance(condcode, int):
        try:
            code_key = chr(condcode).lower()
        except (ValueError, OverflowError):
            code_key = ""
    else:
        code_key = str(condcode).lower()

    cond = _CONDITION_DATA_CACHE.get(code_key)
    if cond is None and isinstance(condcode, int):
        cond = _CONDITION_DATA_CACHE.get(str(condcode))

    if cond is None:
        return None

    res = cond.copy()
    res["condcode"] = condcode
    return res