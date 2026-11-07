"""Regression tests for command line data-retrieval API selection."""

from __future__ import annotations

import importlib
import sys
from types import ModuleType
from unittest.mock import Mock

import pytest

from buienradar.constants import CONTENT, RAINCONTENT, SUCCESS


@pytest.mark.parametrize(
    ("use_xml", "expected_api"),
    [(False, "json"), (True, "xml")],
)
def test_cli_uses_keyword_only_api(
    use_xml: bool,
    expected_api: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Pass JSON/XML mode through the keyword-only get_data argument."""
    docopt_module = ModuleType("docopt")

    def fake_docopt(*_args: object, **_kwargs: object) -> dict[str, bool | str]:
        """Return deterministic CLI options without optional dependencies."""
        return {
            "-v": False,
            "-vv": False,
            "--latitude": "52.09",
            "--longitude": "5.12",
            "--timeframe": "60",
            "--usexml": use_xml,
        }

    monkeypatch.setattr(docopt_module, "docopt", fake_docopt, raising=False)
    monkeypatch.setitem(sys.modules, "docopt", docopt_module)
    cli_module = importlib.import_module("buienradar.__main__")
    monkeypatch.setattr(cli_module, "docopt", fake_docopt)

    fetch_data = Mock(
        return_value={
            SUCCESS: True,
            CONTENT: "synthetic weather",
            RAINCONTENT: "synthetic precipitation",
        }
    )
    parse_data = Mock(return_value={SUCCESS: True})
    monkeypatch.setattr(cli_module, "get_data", fetch_data)
    monkeypatch.setattr(cli_module, "parse_data", parse_data)

    cli_module.main(argv=[])

    fetch_data.assert_called_once_with(52.09, 5.12, api=expected_api)
    parse_data.assert_called_once_with(
        "synthetic weather",
        "synthetic precipitation",
        52.09,
        5.12,
        60,
        use_xml,
    )
