# Getting started

## What the library does

The package fetches current weather data and multi-day forecasts from Buienradar, finds the nearest station for a coordinate pair, and parses precipitation forecasts for a selected look-ahead period. Both JSON and XML feed formats are supported.

## Installation

Install the package using the distribution method used by your project. This repository snapshot does not contain packaging metadata at its root, so this guide does not prescribe a package-install command or a supported Python-version range.

The library imports `requests`, `vincenty`, and, for XML parsing, `xmltodict`. The command-line module also imports `docopt`.

## Retrieve and parse data

`get_data` retrieves the raw feed content. Pass the same coordinates and API format to `parse_data` to turn that content into structured weather data.

```python
from buienradar.buienradar import get_data, parse_data

latitude = 52.3676
longitude = 4.9041
timeframe = 60

raw = get_data(latitude, longitude, api="json")

if not raw.get("success"):
    raise RuntimeError(f"Buienradar request failed: {raw.get('msg')}")

parsed = parse_data(
    raw.get("content"),
    raw.get("raincontent"),
    latitude,
    longitude,
    timeframe,
    api="json",
)

if not parsed.get("success"):
    raise RuntimeError(f"Could not parse Buienradar data: {parsed.get('msg')}")

weather = parsed["data"]
print("Station:", weather.get("stationname"))
print("Temperature:", weather.get("temperature"))
print("Precipitation forecast:", weather.get("precipitation_forecast"))
```

The example checks both retrieval and parsing status. A successful HTTP request does not guarantee that the feed contains a usable station or a complete forecast.

## Use the XML feed

Set `api="xml"` in both calls:

```python
raw = get_data(latitude, longitude, api="xml")

if raw.get("success"):
    parsed = parse_data(
        raw.get("content"),
        raw.get("raincontent"),
        latitude,
        longitude,
        timeframe,
        api="xml",
    )
```

The older positional `usexml` argument to `parse_data` remains available for compatibility. Prefer the keyword-only `api` argument in new code because it makes the selected format explicit.

## Choose coordinates and timeframe

- Latitude must be in the inclusive range `-90` to `90`.
- Longitude must be in the inclusive range `-180` to `180`.
- The default coordinates are `52.091579, 5.119734`.
- The precipitation forecast timeframe defaults to 60 minutes and must be an integer from 5 through 120.

Invalid coordinate types raise `TypeError`; out-of-range coordinates raise `ValueError`. Invalid timeframe types raise `TypeError`, and timeframes outside the allowed range raise `ValueError`.

## Blocking network calls

The library is synchronous and uses `requests`. Do not call `get_data` directly from an async event loop if the request could block important work. Applications built around an event loop should move the call to a worker thread or use an appropriate asynchronous wrapper.

The current HTTP implementation does not set an explicit request timeout. Network operations can therefore take longer than an application expects; this is an implementation limitation, not a configurable timeout option.

## Error handling

Retrieval functions return dictionaries containing `success`, `msg`, and feed-specific values. Parsing functions return `success`, `msg`, and `data`. Check `success` before consuming `content` or parsed weather fields, and tolerate absent optional keys or values.
