"""Buienradar library to get parsed weather data from buienradar.nl."""
import json
import logging
import math
from datetime import datetime
from zoneinfo import ZoneInfo

import requests
from vincenty import vincenty

from buienradar.constants import (
    __BRCONDITIONS,
    ATTRIBUTION,
    ATTRIBUTION_INFO,
    AVERAGE,
    BAROMETERFC,
    BAROMETERFCNAME,
    BAROMETERFCNAMENL,
    CONDCODE,
    CONDITION,
    CONTENT,
    DATA,
    DATETIME,
    DETAILED,
    DISTANCE,
    EXACT,
    EXACTNL,
    FEELTEMPERATURE,
    FORECAST,
    GROUNDTEMP,
    HEADERS,
    HUMIDITY,
    IMAGE,
    IRRADIANCE,
    MAX_RAIN,
    MAX_TEMP,
    MEASURED,
    MESSAGE,
    MIN_RAIN,
    MIN_TEMP,
    NIGHTTIME,
    PRECIPITATION,
    PRECIPITATION_FORECAST,
    PRESSURE,
    RAIN,
    RAIN_CHANCE,
    RAINCONTENT,
    RAINLAST24HOUR,
    RAINLASTHOUR,
    SNOW,
    STATIONNAME,
    STATUS_CODE,
    SUCCESS,
    SUN_CHANCE,
    TEMPERATURE,
    TIMEFRAME,
    TOTAL,
    VISIBILITY,
    WINDAZIMUTH,
    WINDDIRECTION,
    WINDFORCE,
    WINDGUST,
    WINDSPEED
)
from buienradar.urls import JSON_FEED_URL, json_precipitation_forecast_url

# buienradar date format: '07/26/2017 15:50:00'
# "2019-02-03T19:20:00",
__DATE_FORMAT = '%Y-%m-%dT%H:%M:%S'
__TIMEZONE = 'Europe/Amsterdam'
__ZI_TIMEZONE = ZoneInfo(__TIMEZONE)

# Precomputed lookup table for precipitation intensity 10**((val-109)/32)
# for standard integer values in range 0..255.
_MMU_LOOKUP = [10 ** ((val - 109) / 32) for val in range(256)]

# Performance optimization: precomputed condition templates for day and night.
_COND_CACHE_DAY = {
    code: {
        CONDCODE: code,
        CONDITION: val[0],
        DETAILED: val[1],
        EXACT: val[2],
        EXACTNL: val[3],
        NIGHTTIME: False,
    }
    for code, val in __BRCONDITIONS.items()
}
_COND_CACHE_NIGHT = {
    code: {
        CONDCODE: code,
        CONDITION: val[0],
        DETAILED: val[1],
        EXACT: val[2],
        EXACTNL: val[3],
        NIGHTTIME: True,
    }
    for code, val in __BRCONDITIONS.items()
}

__ACTUAL = "actual"
__STATIONMEASUREMENTS = "stationmeasurements"
__LAT = "lat"
__LON = "lon"
__STATIONID = "stationid"
__STATIONNAME = "stationname"
__ICONURL = "iconurl"
__WEATHERDESCRIPTION = "weatherdescription"
__FORECAST = "forecast"
__FIVEDAYFORECAST = "fivedayforecast"
__MAXTEMPERATUREMIN = "maxtemperatureMin"
__MAXTEMPERATUREMAX = "maxtemperatureMax"
__MINTEMPERATUREMIN = "mintemperatureMin"
__MINTEMPERATUREMAX = "mintemperatureMax"
__RAINCHANCE = "rainChance"
__SUNCHANCE = "sunChance"
__MMRAINMAX = "mmRainMax"
__MMRAINMIN = "mmRainMin"
__WIND = "wind"
__WINDDIRECTION = "windDirection"
__DAY = "day"


def __to_upper(val):
    """Convert val into ucase value."""
    try:
        return val.upper()
    except (AttributeError, ValueError, TypeError):
        return val


def __to_int(val):
    """Convert val into an integer value."""
    try:
        return int(val)
    except (AttributeError, ValueError, TypeError):
        return 0


def __to_float(val, digits):
    """Convert val into float with digits decimal."""
    try:
        return round(float(val), digits)
    except (AttributeError, ValueError, TypeError):
        return float(0)


def __to_float2(val):
    """Convert val into float with 2 decimals."""
    return __to_float(val, 2)


def __to_float1(val):
    """Convert val into float with 1 decimal."""
    return __to_float(val, 1)

def __to_localdatetime(val: str | None) -> datetime | None:
    """
    Convert a station or forecast timestamp to a timezone-aware datetime.

    Legacy timestamps without a suffix are interpreted as Europe/Amsterdam
    local time. ISO 8601 UTC designators (Z) and explicit numeric UTC offsets
    are parsed as timezone-aware timestamps and retain their stated timezone.

    Args:
        val: ISO-like timestamp string.

    Returns:
        A timezone-aware datetime, or None if parsing fails.
    """
    if not isinstance(val, str) or not val:
        return None

    # Buienradar's station timestamp uses a trailing Z while its clock
    # value represents Europe/Amsterdam local time. Interpret that suffix
    # as a feed quirk and attach the correct Amsterdam offset for the date
    # (including daylight-saving time), rather than treating the clock value
    # as UTC and shifting the displayed time.
    has_z_suffix = val.endswith("Z")
    timestamp = val[:-1] if has_z_suffix else val

    try:
        parsed_dt = datetime.fromisoformat(timestamp)
    except ValueError:
        return None

    if has_z_suffix or parsed_dt.tzinfo is None:
        return parsed_dt.replace(tzinfo=__ZI_TIMEZONE)

    # Preserve explicit numeric UTC offsets supplied by the feed.
    return parsed_dt

def __getBarFC(pressure):
    """Parse the pressure and return FC (numerical)."""
    if pressure is None:
        return 0
    try:
        press = __to_float1(pressure)
    except:     # noqa E722
        return 0

    if press < 974:
        return 1
    if press < 990:
        return 2
    if press < 1002:
        return 3
    if press < 1010:
        return 4
    if press < 1022:
        return 5
    if press < 1035:
        return 6
    return 7


def __getBarFCName(pressure):
    """Parse the pressure and return FC (String)."""
    if pressure is None:
        return None
    try:
        press = __to_float1(pressure)
    except:     # noqa E722
        return None

    if press < 974:
        return "Thunderstorms"
    if press < 990:
        return "Stormy"
    if press < 1002:
        return "Rain"
    if press < 1010:
        return "Cloudy"
    if press < 1022:
        return "Unstable"
    if press < 1035:
        return "Stable"
    return "Very dry"


def __getBarFCNameNL(pressure):
    """Parse the pressure and return FC in Dutch (String)."""
    if pressure is None:
        return None
    try:
        press = __to_float1(pressure)
    except:     # noqa E722
        return None

    if press < 974:
        return "Zware storm"
    if press < 990:
        return "Storm"
    if press < 1002:
        return "Regen en wind"
    if press < 1010:
        return "Bewolkt"
    if press < 1022:
        return "Veranderlijk"
    if press < 1035:
        return "Mooi"
    return "Zeer mooi"


# SENSOR_TYPES = { 'key': ['key in buienradar json', conversion function], }
SENSOR_TYPES = {
    BAROMETERFC: ['airpressure', __getBarFC],
    BAROMETERFCNAME: ['airpressure', __getBarFCName],
    BAROMETERFCNAMENL: ['airpressure', __getBarFCNameNL],
    HUMIDITY: ['humidity', __to_int],
    GROUNDTEMP: ['groundtemperature', __to_float1],
    IRRADIANCE: ['sunpower', __to_int],
    MEASURED: ['timestamp', __to_localdatetime],
    PRECIPITATION: ['precipitation', __to_float1],
    PRESSURE: ['airpressure', __to_float2],
    STATIONNAME: ['stationname', None],
    CONDITION: ['weatherdescription', None],
    RAINLAST24HOUR: ['rainFallLast24Hour', __to_float1],
    RAINLASTHOUR: ['rainFallLastHour', __to_float1],
    TEMPERATURE: ['temperature', __to_float1],
    FEELTEMPERATURE: ['feeltemperature', __to_float1],
    VISIBILITY: ['visibility', __to_int],
    WINDSPEED: ['windspeed', __to_float2],
    WINDFORCE: ['windspeedBft', __to_int],
    WINDDIRECTION: ['winddirection', __to_upper],
    WINDAZIMUTH: ['winddirectiondegrees', __to_int],
    WINDGUST: ['windgusts', __to_float2],
}

# Performance optimization: precompute validation fields for __is_valid.
# Filtering keys (excluding CONDITION, STATIONNAME, MEASURED) and checking func is not None
# once at import avoids dictionary iterating and branch checks per station validation call.
_VALIDATION_FIELDS = tuple(
    (value, func)
    for key, [value, func] in SENSOR_TYPES.items()
    if key not in (CONDITION, STATIONNAME, MEASURED) and func is not None
)


log = logging.getLogger(__name__)


def get_json_data(latitude=52.091579, longitude=5.119734):
    """Get buienradar json data and return results."""
    final_result = {SUCCESS: False,
                    MESSAGE: None,
                    CONTENT: None,
                    RAINCONTENT: None}

    log.debug("Getting buienradar json data for latitude=%s, longitude=%s",
              latitude, longitude)
    result = __get_ws_data()

    if result[SUCCESS]:
        # store json data:
        final_result[CONTENT] = result[CONTENT]
        final_result[SUCCESS] = True
    else:
        if STATUS_CODE in result and MESSAGE in result:
            msg = "Status: %d, Msg: %s" % (result[STATUS_CODE],
                                           result[MESSAGE])
        elif MESSAGE in result:
            msg = "Msg: %s" % (result[MESSAGE])
        else:
            msg = "Something went wrong (reason unknown)."

        log.warning(msg)
        final_result[MESSAGE] = msg

    # load forecasted precipitation:
    result = __get_precipfc_data(latitude,
                                 longitude)
    if result[SUCCESS]:
        final_result[RAINCONTENT] = result[CONTENT]
    else:
        if STATUS_CODE in result and MESSAGE in result:
            msg = "Status: %d, Msg: %s" % (result[STATUS_CODE],
                                           result[MESSAGE])
        elif MESSAGE in result:
            msg = "Msg: %s" % (result[MESSAGE])
        else:
            msg = "Something went wrong (reason unknown)."

        log.warning(msg)
        final_result[MESSAGE] = msg

    return final_result


def parse_json_data(content, raincontent, latitude=52.091579,
                    longitude=5.119734, timeframe=60):
    """Parse the raw data and return as data dictionary."""
    result = {SUCCESS: False, MESSAGE: None, DATA: None}

    if timeframe < 5 or timeframe > 120:
        raise ValueError("Timeframe must be >=5 and <=120.")

    if content is not None:
        try:
            json_content = json.loads(content)
        except json.JSONDecodeError as err:
            result[MESSAGE] = "Unable to parse content as json."
            log.error("Unable to parse content as json. %s", err)
            return result

        result = __parse_ws_data(json_content, latitude, longitude)

        if result[SUCCESS] and raincontent is not None:
            data = __parse_precipfc_data(raincontent, timeframe)
            result[DATA][PRECIPITATION_FORECAST] = data

    log.debug("Extracted weather-data: %s", result[DATA])
    return result


def __get_ws_data():
    """Get buienradar json data and return results."""
    return __get_url(JSON_FEED_URL)


def __get_precipfc_data(latitude, longitude):
    """Get buienradar forecasted precipitation."""
    return __get_url(json_precipitation_forecast_url(latitude, longitude))


def __get_url(url, fetch=True):
    """Load json data from url and return result."""
    log.debug("Retrieving  weather data (%s)...", url)
    result = {SUCCESS: False, MESSAGE: None}
    try:
        r = requests.get(url)
        result[STATUS_CODE] = r.status_code
        result[HEADERS] = r.headers
        if fetch:
            result[CONTENT] = r.text
        if (200 == r.status_code):
            result[SUCCESS] = True
        else:
            result[MESSAGE] = "Got http statuscode: %d." % (r.status_code)
        return result
    except requests.RequestException as ose:
        result[MESSAGE] = 'Error getting url data. %s' % ose
        log.error(result[MESSAGE])

    return result


def __parse_ws_data(jsondata, latitude=52.091579, longitude=5.119734):
    """Parse the buienradar json and rain data."""
    log.debug("Parse ws data: latitude: %s, longitude: %s",
              latitude, longitude)
    result = {SUCCESS: False, MESSAGE: None, DATA: None}

    # select the nearest weather station and its exact distance
    loc_data, dist = __select_nearest_ws(jsondata, latitude, longitude)
    # process current weather data from selected weatherstation
    if not loc_data:
        result[MESSAGE] = 'No location selected.'
        return result

    if not __is_valid(loc_data):
        result[MESSAGE] = 'Location data is invalid.'
        return result

    # add distance to weatherstation (reuse dist calculated in __select_nearest_ws)
    log.debug("Raw location data: %s", loc_data)
    result[DISTANCE] = dist
    result = __parse_loc_data(loc_data, result)

    # extract weather forecast
    try:
        fc_data = jsondata[__FORECAST][__FIVEDAYFORECAST]
    except (json.JSONDecodeError, KeyError):
        result[MESSAGE] = 'Unable to extract forecast data.'
        log.exception(result[MESSAGE])
        return result

    if fc_data:
        # result = __parse_fc_data(fc_data, result)
        log.debug("Raw forecast data: %s", fc_data)
        # pylint: disable=unsupported-assignment-operation
        result[DATA][FORECAST] = __parse_fc_data(fc_data)

    return result


def __parse_loc_data(loc_data, result):
    """Parse the json data from selected weatherstation."""
    result[DATA] = {ATTRIBUTION: ATTRIBUTION_INFO,
                    FORECAST: [],
                    PRECIPITATION_FORECAST: None}

    for key, [value, func] in SENSOR_TYPES.items():
        result[DATA][key] = None
        try:
            sens_data = loc_data[value]
            if key == CONDITION:
                # update weather symbol & status text
                # desc = loc_data[__WEATHERDESCRIPTION]
                # result[DATA][CONDITION] = __cond_from_desc(desc)
                #
                # test clear-->sunny vs clear-->clear-night
                # loc_data[__ICONURL] =
                #   "https://www.buienradar.nl/resources/images/icons/weather/30x30/a.png"
                # loc_data[__ICONURL] =
                #   "https://www.buienradar.nl/resources/images/icons/weather/30x30/aa.png"
                result[DATA][CONDITION] = __cond_from_image(
                    loc_data[__ICONURL])
                if result[DATA][CONDITION]:
                    result[DATA][CONDITION][IMAGE] = loc_data[__ICONURL]

                continue
            if key == STATIONNAME:
                result[DATA][key] = __getStationName(loc_data[__STATIONNAME],
                                                     loc_data[__STATIONID])
                continue
            # update all other data:
            if func is not None:
                result[DATA][key] = func(sens_data)
            else:
                result[DATA][key] = sens_data
        except KeyError:
            log.debug("Data element with key='%s' "
                      "not loaded from br data!", key)
    result[SUCCESS] = True
    return result


_WIND_SPEEDS = {
    0: 0.25, 1: 0.51, 2: 2.06, 3: 3.6, 4: 5.66,
    5: 8.23, 6: 11.32, 7: 14.4, 8: 17.49, 9: 21.09,
    10: 24.69, 11: 28.81, 12: 32.41,
}

_WIND_DIRECTIONS = {
    'N': 0, 'NNO': 22.5, 'NO': 45, 'ONO': 67.5, 'O': 90,
    'OZO': 112.5, 'ZO': 135, 'ZZO': 157.5, 'Z': 180,
    'ZZW': 202.5, 'ZW': 225, 'WZW': 247.5, 'W': 270,
    'WNW': 292.5, 'NW': 315, 'NNW': 237.5,
    'NNE': 22.5, 'NE': 45, 'ENE': 67.5, 'E': 90,
    'ESE': 112.5, 'SE': 135, 'SSE': 157.5, 'S': 180,
    'SSW': 202.5, 'SW': 225, 'WSW': 247.5,
}


def __parse_fc_data(fc_data):
    """Parse the forecast data from the json section."""
    fc = []
    # Performance optimization: extract wind direction, icon URL, and wind force once per day
    # to avoid redundant string upper() conversions and repeated dictionary lookups.
    for day in fc_data:
        wind_str = __get_str(day, __WINDDIRECTION)
        wind_dir_upper = wind_str.upper()
        wind_force = __get_int(day, __WIND)
        icon_url = __get_str(day, __ICONURL)

        cond = __cond_from_image(icon_url)
        if cond:
            cond[NIGHTTIME] = False
            cond[IMAGE] = icon_url

        fcdata = {
            CONDITION: cond,
            TEMPERATURE: __get_avr_float(day, __MAXTEMPERATUREMIN,
                                         __MAXTEMPERATUREMAX),
            MIN_TEMP: __get_float(day, __MINTEMPERATUREMIN),
            MAX_TEMP: __get_float(day, __MAXTEMPERATUREMAX),
            SUN_CHANCE: __get_int(day, __SUNCHANCE),
            RAIN_CHANCE: __get_int(day, __RAINCHANCE),
            RAIN: __get_avr_float(day, __MMRAINMIN, __MMRAINMAX),
            MIN_RAIN: __get_float(day, __MMRAINMIN),  # new
            MAX_RAIN: __get_float(day, __MMRAINMAX),  # new
            # depricated / for compatibility:
            SNOW: 0,
            WINDFORCE: wind_force,
            # new: est. windspeed (m/s) from windforce (Bft):
            WINDSPEED: __get_windspeed(wind_force),
            # new: ONO/NW:
            WINDDIRECTION: wind_dir_upper,
            # new; estimated windazimuth using __WINDDIRECTION:
            WINDAZIMUTH: __get_windazimuth(wind_dir_upper),
            DATETIME: __to_localdatetime(__get_str(day, __DAY)),
        }

        fc.append(fcdata)
    return fc


def __get_windspeed(windforce):
    try:
        return _WIND_SPEEDS[windforce]
    except (KeyError, TypeError):
        return None


def __get_windazimuth(winddirection):
    """Get an estimate wind azimuth using the winddirection string."""
    if not winddirection:
        return None

    try:
        return _WIND_DIRECTIONS[winddirection.upper()]
    except (KeyError, AttributeError, TypeError):
        return None


def __get_str(section, name):
    """Get the forecasted string from json section."""
    try:
        return section[name]
    except (ValueError, TypeError, KeyError):
        return ""


def __get_float(section, name):
    """Get the forecasted float from json section."""
    try:
        return float(section[name])
    except (ValueError, TypeError, KeyError):
        return float(0)


def __get_avr_float(section, name1, name2):
    """Get the forecasted float from json section."""
    try:
        val1 = float(section[name1])
    except (ValueError, TypeError, KeyError):
        val1 = None
    try:
        val2 = float(section[name2])
    except (ValueError, TypeError, KeyError):
        val2 = None

    if (val1 is not None and val2 is not None):
        return (val1 + val2) / 2
    if (val1 is not None):
        return val1
    return val2


def __get_int(section, name):
    """Get the forecasted int from json section."""
    try:
        return int(section[name])
    except (ValueError, TypeError, KeyError):
        return 0


def __parse_precipfc_data(data, timeframe):
    """Parse the forecasted precipitation data."""
    result = {AVERAGE: None, TOTAL: None, TIMEFRAME: None}

    log.debug("Precipitation data: %s", data)
    lines = data.splitlines()
    totalrain = 0.0
    numberoflines = 0
    nrlines = min(len(lines), round(float(timeframe) / 5) + 1)
    # looping through lines of forecasted precipitation data and
    # not using the time data (HH:MM) int the data. This is to allow for
    # correct data in case we are running in a different timezone.
    # Performance optimization:
    # Use precomputed lookup table `_MMU_LOOKUP` for integer values 0..255
    # (formula: 10**((val-109)/32)) to avoid expensive exponentiation per line.
    for index in range(1, nrlines):
        line = lines[index]
        log.debug("__parse_precipfc_data: line: %s", line)
        parts = line.split("|")
        if len(parts) != 2:
            log.warning("Skipping malformed precipitation line: %r", line)
            continue
        val_str = parts[0]
        # See buienradar documentation for this api, attribution
        # https://www.buienradar.nl/overbuienradar/gratis-weerdata
        #
        # Op basis van de door u gewenste coordinaten (latitude en longitude)
        # kunt u de neerslag tot twee uur vooruit ophalen in tekstvorm. De
        # data wordt iedere 5 minuten geupdatet. Op deze pagina kunt u de
        # neerslag in tekst vinden. De waarde 0 geeft geen neerslag aan (droog)
        # de waarde 255 geeft zware neerslag aan. Gebruik de volgende formule
        # voor het omrekenen naar de neerslagintensiteit in de eenheid
        # millimeter per uur (mm/u):
        #
        # Neerslagintensiteit = 10^((waarde-109)/32)
        #
        # Ter controle: een waarde van 77 is gelijk aan een neerslagintensiteit
        # van 0,1 mm/u.
        try:
            val_int = int(val_str)
            if 0 <= val_int <= 255:
                mmu = _MMU_LOOKUP[val_int]
            else:
                mmu = 10 ** ((val_int - 109) / 32)
        except ValueError:
            try:
                val_float = float(val_str.replace(',', '.'))
                mmu = 10 ** ((val_float - 109) / 32)
            except ValueError:
                log.warning("Skipping invalid numeric precipitation value: %r", line)
                continue

        totalrain += mmu
        numberoflines += 1

    if numberoflines > 0:
        result[AVERAGE] = round((totalrain / numberoflines), 2)
    else:
        result[AVERAGE] = 0
    result[TOTAL] = round(totalrain / 12, 2)
    result[TIMEFRAME] = timeframe

    return result


def __cond_from_image(img):
    """Get the condition from the image url."""
    # the image url should be something like:
    # - http://somehost/somefolder/cc.png (night time)
    # - http://somehost/somefolder/CC.png
    # - http://somehost/somefolder/c.png (day time)
    # - http://somehost/somefolder/C.png
    #  if there is not url or the length is too small,
    #  we cannot determine the condition.
    if img is None or len(img) < 6:
        return None
    image = img.lower()
    code = image[-5:-4]
    night = (image[-6:-5] == code)
    cache = _COND_CACHE_NIGHT if night else _COND_CACHE_DAY
    cond = cache.get(code)
    return cond.copy() if cond is not None else None


def __select_nearest_ws(jsondata, latitude, longitude):
    """Select the nearest weatherstation."""
    log.debug("__select_nearest_ws: latitude: %s, longitude: %s",
              latitude, longitude)

    try:
        ws_json = jsondata[__ACTUAL]
        ws_json = ws_json[__STATIONMEASUREMENTS]
    except (KeyError, TypeError):
        log.warning("Missing section in Buienradar jsondata (%s)."
                    "Can happen 00:00-01:00 CE(S)T",
                    __STATIONMEASUREMENTS)
        return None, None

    # Performance optimization:
    # `vincenty` distance calculation is computationally expensive.
    # Pre-filter stations using fast equirectangular distance approximation
    # to select top candidate stations before running exact geodesic vincenty.
    cos_lat = math.cos(math.radians(latitude))
    candidates = []

    for wstation in ws_json:
        try:
            wslat = float(wstation[__LAT])
            wslon = float(wstation[__LON])
            dy = wslat - latitude
            dx = (wslon - longitude) * cos_lat
            approx_sq = dx * dx + dy * dy
            candidates.append((approx_sq, wstation))
        except (ValueError, TypeError, KeyError):
            continue

    if not candidates:
        log.warning("No weatherstation selected; aborting...")
        return None, None

    candidates.sort(key=lambda item: item[0])

    dist = None
    loc_data = None

    # Evaluate exact vincenty distance on top 3 candidate stations
    for _, wstation in candidates[:3]:
        dist2 = __get_ws_distance(wstation, latitude, longitude)
        if dist2 is not None:
            if loc_data is None or dist2 < dist:
                dist = dist2
                loc_data = wstation

    if loc_data is None:
        log.warning("No weatherstation selected; aborting...")
        return None, None
    else:
        try:
            log.debug("Selected weatherstation: code='%s', "
                      "name='%s', lat='%s', lon='%s'.",
                      loc_data[__STATIONID],
                      loc_data[__STATIONNAME],
                      loc_data[__LAT],
                      loc_data[__LON])
        except KeyError:
            log.debug("Selected weatherstation")
        return loc_data, dist


def __get_ws_distance(wstation, latitude, longitude):
    """
    Get the distance to the weatherstation from wstation section of json.

    wstation: weerstation section of buienradar json (dict)
    latitude: our latitude
    longitude: our longitude
    """
    if wstation:
        try:
            wslat = float(wstation[__LAT])
            wslon = float(wstation[__LON])

            dist = vincenty((latitude, longitude), (wslat, wslon))
            log.debug("calc distance: %s (latitude: %s, longitude: "
                      "%s, wslat: %s, wslon: %s)", dist, latitude,
                      longitude, wslat, wslon)
            return dist
        except (ValueError, TypeError, KeyError):
            # value does not exist, or is not a float
            return None
    else:
        return None


def __is_valid(loc_data):
    """Determine if this can be valid data (not all 0's)."""
    # Use precomputed validation fields to avoid repeated dictionary and key filtering
    for value, func in _VALIDATION_FIELDS:
        sens_data = loc_data.get(value)
        if sens_data is not None:
            val = func(sens_data)
            if val is not None and val != 0 and val != "":
                return True


def __getStationName(name, id):
    """Construct a station name."""
    name = name.replace("Meetstation", "")
    name = name.strip()
    name += " (%s)" % id
    return name
