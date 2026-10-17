# buienradar

Python package for retrieving and parsing weather data from Buienradar.

## Documentation

Start with the [documentation index](docs/README.md):

- [Getting started](docs/getting-started.md)
- [API reference](docs/api-reference.md)
- [Parsed data model](docs/data-model.md)

## Quick example

```python
from buienradar.buienradar import get_data, parse_data

latitude, longitude = 52.3676, 4.9041
raw = get_data(latitude, longitude, api="json")

if raw.get("success"):
    result = parse_data(
        raw.get("content"),
        raw.get("raincontent"),
        latitude,
        longitude,
        timeframe=60,
        api="json",
    )
    if result.get("success"):
        print(result["data"])
```

Check the `success` field in each result before consuming its data. See the documentation for return structures, supported feed formats, and current limitations.
