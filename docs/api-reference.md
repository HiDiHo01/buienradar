# API reference

The supported public functions are exported by `buienradar.buienradar`.

## `get_data(latitude=52.091579, longitude=5.119734, *, api="json")`

Retrieve raw weather and precipitation-feed content.

### Arguments

| Argument | Type | Default | Description |
| --- | --- | --- | --- |
| `latitude` | `float` | `52.091579` | Latitude in decimal degrees, from -90 to 90. |
| `longitude` | `float` | `5.119734` | Longitude in decimal degrees, from -180 to 180. |
| `api` | `"json"` or `"xml"` | `"json"` | Selects the weather feed format. |

### Return value

A dictionary with these keys:

- `success`: whether the main weather feed request succeeded.
- `msg`: error or status text, or `None`.
- `content`: raw weather-feed text, or `None`.
- `raincontent`: raw precipitation-forecast text, or `None`.

The implementation attempts to retrieve precipitation forecast content separately. A failure of that secondary request may populate `msg` even when the main weather feed succeeded. Check the values you need rather than assuming that `success` guarantees both payloads are present.

### Errors

Invalid coordinate types raise `TypeError`; coordinates outside the allowed ranges raise `ValueError`. HTTP and request exceptions are represented in the returned dictionary. Network calls are synchronous.

## `parse_data(content, raincontent, latitude=52.091579, longitude=5.119734, timeframe=60, usexml=None, *, api=None)`

Parse raw feed content returned by `get_data`.

### Arguments

| Argument | Description |
| --- | --- |
| `content` | Raw weather feed text. |
| `raincontent` | Raw precipitation forecast text, or `None`. |
| `latitude`, `longitude` | Coordinates used to select the nearest station. |
| `timeframe` | Precipitation forecast look-ahead in minutes; integer from 5 through 120. |
| `usexml` | Legacy format selector. When `api` is omitted, a truthy value selects XML; otherwise JSON is used. |
| `api` | Keyword-only `"json"` or `"xml"` selector. Takes precedence over `usexml`. |

### Return value

A dictionary containing:

- `success`: whether parsing produced usable weather data.
- `msg`: parse failure details or `None`.
- `data`: structured weather fields when successful, otherwise generally `None`.
- `distance`: distance to the selected weather station when available.

See [Data model](data-model.md) for the fields nested under `data`.

### Errors and failure results

Invalid coordinate types/ranges and invalid timeframe types/ranges raise `TypeError` or `ValueError`. Malformed or incomplete upstream payloads are generally reported in the result dictionary with `success=False` and a message. Optional upstream fields may be absent or mapped to `None` or a default value.

## `condition_from_code(condcode)`

Return condition metadata from the package's condition mapping, or `None` when no mapping is found.

The metadata structure contains `condcode`, `condition`, `detailed`, `exact`, and `exactnl`. The current function signature declares an integer argument, while the internal mapping is keyed by one-character strings; callers should verify this behavior against the version they use before relying on numeric condition-code lookups.

## Feed URL helpers

The `buienradar.urls` module defines internal feed URL constants and these helper functions:

- `json_precipitation_forecast_url(latitude, longitude)`
- `xml_precipitation_forecast_url(latitude, longitude)`
- `radar_url(width=500, height=512)`

The precipitation URL helpers round coordinates to two decimal places. `radar_url` validates width (120–700) and height (120–765), raising `ValueError` outside those bounds. These helpers are in a separate module and are not listed in the package's `__all__`; check compatibility requirements before treating them as stable public API.
