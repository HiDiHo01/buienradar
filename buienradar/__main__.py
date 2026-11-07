"""
Command line interface for buienradar library.
"""
from __future__ import annotations

import logging
import sys
from importlib.metadata import version, PackageNotFoundError
from typing import Sequence

from docopt import docopt

from .buienradar import get_data, parse_data
from .constants import CONTENT, MESSAGE, RAINCONTENT, SUCCESS


def _configure_logging(verbosity: int) -> None:
    """Configure logging level based on verbosity count."""
    level = logging.ERROR
    if verbosity == 1:
        level = logging.INFO
    elif verbosity >= 2:
        level = logging.DEBUG

    logging.basicConfig(level=level)


def _get_version() -> str:
    """Retrieve installed package version."""
    try:
        return version("buienradar")
    except PackageNotFoundError:
        return "unknown"


def main(argv: Sequence[str] | None = None) -> None:
    """
    Parse arguments and execute CLI logic.
    """
    if argv is None:
        argv = sys.argv[1:]

    args = docopt(__doc__, argv=argv, version=_get_version())

    verbosity = 0
    if args["-v"]:
        verbosity = 1
    if args["-vv"]:
        verbosity = 2

    _configure_logging(verbosity)
    logger = logging.getLogger(__name__)
    logger.info("Starting CLI")

    try:
        latitude = float(args["--latitude"])
        longitude = float(args["--longitude"])
        timeframe = int(args["--timeframe"])
    except (TypeError, ValueError) as exc:
        logger.error("Invalid numeric argument: %s", exc)
        sys.exit(1)

    if not 5 <= timeframe <= 120:
        logger.error("Timeframe must be between 5 and 120 minutes")
        sys.exit(1)

    usexml = bool(args["--usexml"])

    result = get_data(latitude, longitude, usexml)

    if not result.get(SUCCESS):
        logger.error(
            "Retrieving weather data failed: %s",
            result.get(MESSAGE),
        )
        sys.exit(1)

    logger.debug("Retrieved data: %s", result)

    parsed = parse_data(
        result[CONTENT],
        result[RAINCONTENT],
        latitude,
        longitude,
        timeframe,
        usexml,
    )

    logger.info("Result: %s", parsed)
    print(parsed)


if __name__ == "__main__":
    main()