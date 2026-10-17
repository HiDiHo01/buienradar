# Data model

This page documents the dictionary keys defined in `buienradar/constants.py` and populated by the JSON and XML parsers. The upstream feeds do not expose identical fields, so some values are format-specific or may be missing.

## Top-level parsed result

`parse_data(...)` returns a dictionary with the following common keys:

| Key | Meaning |
| --- | --- |
| `success` | `True` when the parser successfully selected and parsed a usable station. |
| `msg` | Error detail, or `None`. |
| `data` | Parsed weather dictionary on success; otherwise generally `None`. |
| `distance` | Distance to the selected weather station when available. |

## Current weather: `data`

| Key | Meaning |
| --- | --- |
| `attribution` | Attribution text: `Data provided by buienradar.nl`. |
| `stationname` | Selected station name. |
| `measured` | Time the station measurement was recorded, as a timezone-aware `datetime` when parsing succeeds. |
| `temperature` | Air temperature. |
| `feeltemperature` | Feels-like temperature; JSON-feed field. |
| `groundtemperature` | Ground temperature. |
| `humidity` | Relative humidity. |
| `pressure` | Air pressure. |
| `barometerfc`, `barometerfcname`, `barometerfcnamenl` | Pressure-derived weather classification; JSON-feed fields. |
| `precipitation` | Current precipitation intensity from the selected station. |
| `rainlast24hour`, `rainlasthour` | Rainfall accumulation fields; JSON-feed fields. |
| `irradiance` | Solar irradiance / sun power. |
| `visibility` | Visibility. |
| `windspeed` | Wind speed. |
| `windforce` | Wind force, generally represented as Beaufort force. |
| `winddirection` | Wind direction as a direction string where provided. |
| `windazimuth` | Wind direction in degrees where provided or estimated. |
| `windgust` | Wind gust speed. |
| `condition` | Condition metadata derived from the feed's icon/condition information. |
| `forecast` | List of forecast entries. |
| `precipitation_forecast` | Short-term precipitation forecast summary, or `None` if not available. |

The parsers initialize many optional values to `None`. Do not assume that every field has a usable value for every feed or station.

## Condition metadata

The `condition` field is a dictionary when the icon code is recognized. It can contain:

- `condcode`: condition code.
- `condition`: broad condition category.
- `detailed`: detailed condition identifier.
- `exact`: English description.
- `exact_nl`: Dutch description.
- `night`: whether the icon indicates night.
- `image`: source icon URL, when supplied by the feed.

If the feed does not contain a recognized icon code, the condition may be `None`.

## Daily forecast entries

Each item in `data["forecast"]` is a dictionary. Depending on the selected feed, it may contain:

| Key | Meaning |
| --- | --- |
| `datetime` | Forecast date/time as a timezone-aware `datetime` when parsing succeeds. |
| `condition` | Condition metadata for the forecast. |
| `temperature` | Forecast temperature value; the JSON parser derives this from available maximum-temperature fields. |
| `mintemp`, `maxtemp` | Minimum and maximum temperature. |
| `rain` | Forecast rainfall amount or estimate. |
| `minrain`, `maxrain` | Minimum and maximum rainfall estimates in JSON forecast data. |
| `rainchance` | Chance of rain. |
| `sunchance` | Chance of sunshine. |
| `snow` | Legacy compatibility field; the JSON parser currently sets this to zero. |
| `windforce` | Forecast wind force. |
| `windspeed` | Estimated wind speed where calculated by the JSON parser. |
| `winddirection`, `windazimuth` | Forecast direction text and estimated degrees in JSON data. |

Not every key is produced by both formats. Check the actual returned dictionary for the feed you selected.

## Short-term precipitation forecast

`data["precipitation_forecast"]` is either `None` or a dictionary with:

| Key | Meaning |
| --- | --- |
| `average` | Average calculated precipitation intensity in mm/h for the selected samples. |
| `total` | Calculated total estimate over the requested period. |
| `timeframe` | Requested look-ahead duration in minutes. |

The upstream precipitation feed is sampled in five-minute intervals and is intended to provide up to two hours of near-term precipitation information. The parser converts each feed value to an intensity using the formula documented in the source, then calculates an average and an estimate for the requested timeframe. These are feed-derived estimates, not guarantees of actual rainfall.

## Timestamps and time zones

The parsers return timezone-aware datetimes using the `Europe/Amsterdam` timezone for timestamps they interpret as local station/forecast time. The JSON parser has special handling for the feed's trailing `Z` station timestamp: it treats the clock value as Amsterdam local time rather than converting it as UTC. Explicit numeric offsets in JSON timestamps are preserved.

Because timestamp interpretation is tied to the upstream feed's conventions, consumers should not strip timezone information or assume that all feed timestamps use the same convention.

## Retrieval result versus parsed result

Do not confuse the raw retrieval dictionary from `get_data` with the parsed dictionary from `parse_data`:

- Raw result: `success`, `msg`, `content`, `raincontent`.
- Parsed result: `success`, `msg`, `data`, and optionally `distance`.

The raw response contains upstream text. Parsed values are normalized by the library and may include derived or defaulted values.
