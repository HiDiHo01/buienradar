# Buienradar Python library documentation

This documentation describes the public API and data structures of the `buienradar` Python package in this repository.

## Guides

- [Getting started](getting-started.md) — retrieve and parse weather data with JSON or XML.
- [API reference](api-reference.md) — public functions, arguments, return values, and errors.
- [Data model](data-model.md) — parsed weather fields, forecasts, precipitation, timestamps, and format differences.

## Project overview

The package retrieves weather feeds from Buienradar, selects the weather station nearest to supplied coordinates, and converts current observations and forecasts into Python dictionaries. It supports the JSON and XML feed paths and a separate precipitation-forecast endpoint.

This is a synchronous Python library, not a Home Assistant custom integration. Call network-facing functions outside an event loop's critical path; a Home Assistant consumer should offload blocking calls or provide an asynchronous boundary.

## Important behavior

- Coordinates are latitude and longitude in decimal degrees.
- The parsed precipitation forecast timeframe must be between 5 and 120 minutes.
- Returned dictionaries use string keys documented in the [data model](data-model.md).
- Upstream feed availability and payload shape are outside this package's control. Always check the `success` flag and handle missing data.
- The current implementation uses `requests.get` without an explicit timeout; callers should account for the possibility of slow network requests.

For contribution and repository workflow rules, see [CONTRIBUTING.md](../CONTRIBUTING.md), [AGENTS.md](../AGENTS.md), and [AI_POLICY.md](../AI_POLICY.md).
