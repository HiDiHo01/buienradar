"""Tests for weather station distance calculation and nearest station selection."""
import pytest
from buienradar.buienradar_json import __select_nearest_ws as json_select_nearest
from buienradar.buienradar_xml import __select_nearest_ws as xml_select_nearest


def test_json_nearest_ws_selection():
    """Test JSON station selection accuracy and edge cases."""
    jsondata = {
        "actual": {
            "stationmeasurements": [
                {
                    "stationid": 6260,
                    "stationname": "De Bilt",
                    "lat": "52.10",
                    "lon": "5.18",
                },
                {
                    "stationid": 6240,
                    "stationname": "Schiphol",
                    "lat": "52.32",
                    "lon": "4.79",
                },
                {
                    "stationid": 6380,
                    "stationname": "Maastricht",
                    "lat": "50.91",
                    "lon": "5.77",
                },
                {
                    "stationid": 9999,
                    "stationname": "Invalid",
                    "lat": "invalid",
                    "lon": "invalid",
                },
            ]
        }
    }

    # Location near De Bilt (52.09, 5.12)
    selected = json_select_nearest(jsondata, 52.09, 5.12)
    assert selected is not None
    assert selected["stationid"] == 6260
    assert selected["stationname"] == "De Bilt"

    # Location near Maastricht (50.90, 5.75)
    selected_m = json_select_nearest(jsondata, 50.90, 5.75)
    assert selected_m is not None
    assert selected_m["stationid"] == 6380

    # Test empty / invalid payloads
    assert json_select_nearest({}, 52.0, 5.0) is None
    assert json_select_nearest({"actual": {}}, 52.0, 5.0) is None


def test_xml_nearest_ws_selection():
    """Test XML station selection accuracy and edge cases."""
    xmldata = {
        "weergegevens": {
            "actueel_weer": {
                "weerstations": {
                    "weerstation": [
                        {
                            "stationcode": "6260",
                            "stationnaam": {"#text": "Meetstation De Bilt"},
                            "lat": "52.10",
                            "lon": "5.18",
                        },
                        {
                            "stationcode": "6240",
                            "stationnaam": {"#text": "Meetstation Schiphol"},
                            "lat": "52.32",
                            "lon": "4.79",
                        },
                        {
                            "stationcode": "6380",
                            "stationnaam": {"#text": "Meetstation Maastricht"},
                            "lat": "50.91",
                            "lon": "5.77",
                        },
                    ]
                }
            }
        }
    }

    # Location near De Bilt (52.09, 5.12)
    selected = xml_select_nearest(xmldata, 52.09, 5.12)
    assert selected is not None
    assert selected["stationcode"] == "6260"

    # Location near Schiphol (52.30, 4.80)
    selected_s = xml_select_nearest(xmldata, 52.30, 4.80)
    assert selected_s is not None
    assert selected_s["stationcode"] == "6240"

    # Test empty / invalid payloads
    assert xml_select_nearest({}, 52.0, 5.0) is None
