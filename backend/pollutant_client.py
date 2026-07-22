"""
Live pollutant readings, tried in this order:

  1. OpenWeather Air Pollution API — free tier, global coverage, returns
     already-computed raw pollutant concentrations in ug/m3 (no CPCB
     breakpoint inversion needed, unlike sub-index feeds). Docs:
     https://openweathermap.org/api/air-pollution. Needs OPENWEATHER_API_KEY
     in backend/.env.

  2. Per-city mock baseline -- used if the OpenWeather call fails or the key
     is missing, so the app never breaks.

UNIT NOTE: OpenWeather's "co" field is reported in ug/m3, but our CO feature
(and the CPCB breakpoint table used elsewhere in this codebase) is in mg/m3.
We divide by 1000 to convert. OpenWeather does not report a combined "NOx"
figure, so we approximate it as NO + NO2 when both are present.
"""
import os
import time
import requests

# ---- CPCB breakpoint tables (kept here only for reference / other modules that import them) ----
BREAKPOINTS = {
    'PM2.5': [(0, 30, 0, 50), (30, 60, 50, 100), (60, 90, 100, 200), (90, 120, 200, 300), (120, 250, 300, 400), (250, 380, 400, 500)],
    'PM10':  [(0, 50, 0, 50), (50, 100, 50, 100), (100, 250, 100, 200), (250, 350, 200, 300), (350, 430, 300, 400), (430, 500, 400, 500)],
    'NO2':   [(0, 40, 0, 50), (40, 80, 50, 100), (80, 180, 100, 200), (180, 280, 200, 300), (280, 400, 300, 400), (400, 500, 400, 500)],
    'SO2':   [(0, 40, 0, 50), (40, 80, 50, 100), (80, 380, 100, 200), (380, 800, 200, 300), (800, 1600, 300, 400), (1600, 2100, 400, 500)],
    'CO':    [(0, 1.0, 0, 50), (1.0, 2.0, 50, 100), (2.0, 10, 100, 200), (10, 17, 200, 300), (17, 34, 300, 400), (34, 50, 400, 500)],
    'O3':    [(0, 50, 0, 50), (50, 100, 50, 100), (100, 168, 100, 200), (168, 208, 200, 300), (208, 748, 300, 400), (748, 1000, 400, 500)],
}

REQUEST_TIMEOUT = 10
MAX_ATTEMPTS = 2
RETRY_BACKOFF_SECONDS = 2


def _get_with_retry(url, params, timeout=REQUEST_TIMEOUT):
    last_exc = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            return requests.get(url, params=params, timeout=timeout)
        except requests.exceptions.RequestException as e:
            last_exc = e
            if attempt < MAX_ATTEMPTS:
                time.sleep(RETRY_BACKOFF_SECONDS * attempt)
    raise last_exc


# OpenWeather "components" keys -> our feature names. NH3 is included;
# OpenWeather has no NOx field, so that's synthesized from NO + NO2 below.
OWM_TO_FEATURE = {
    "pm2_5": "PM2.5", "pm10": "PM10", "no": "NO", "no2": "NO2",
    "so2": "SO2", "co": "CO", "o3": "O3", "nh3": "NH3",
}

# Representative fallback values, per city -- NOT live data, just rough
# city-typical profiles so the demo doesn't collapse to one identical number
# everywhere when no live source is available.
DEFAULT_MOCK = {
    'PM2.5': 65.0, 'PM10': 110.0, 'NO': 15.2, 'NO2': 28.4,
    'NOx': 22.1, 'NH3': 12.5, 'CO': 0.9, 'SO2': 14.3, 'O3': 38.0
}

CITY_MOCK_POLLUTANTS = {
    "Delhi":      {'PM2.5': 168.0, 'PM10': 265.0, 'NO': 28.0, 'NO2': 52.0, 'NOx': 44.0, 'NH3': 22.0, 'CO': 1.8, 'SO2': 12.0, 'O3': 30.0},
    "Mumbai":     {'PM2.5': 62.0,  'PM10': 105.0, 'NO': 14.0, 'NO2': 30.0, 'NOx': 24.0, 'NH3': 10.0, 'CO': 0.8, 'SO2': 11.0, 'O3': 34.0},
    "Bengaluru":  {'PM2.5': 48.0,  'PM10': 88.0,  'NO': 11.0, 'NO2': 24.0, 'NOx': 18.0, 'NH3': 8.0,  'CO': 0.6, 'SO2': 8.0,  'O3': 40.0},
    "Kolkata":    {'PM2.5': 95.0,  'PM10': 160.0, 'NO': 18.0, 'NO2': 35.0, 'NOx': 28.0, 'NH3': 14.0, 'CO': 1.1, 'SO2': 15.0, 'O3': 28.0},
    "Chennai":    {'PM2.5': 52.0,  'PM10': 92.0,  'NO': 12.0, 'NO2': 26.0, 'NOx': 20.0, 'NH3': 9.0,  'CO': 0.7, 'SO2': 10.0, 'O3': 36.0},
    "Hyderabad":  {'PM2.5': 70.0,  'PM10': 120.0, 'NO': 16.0, 'NO2': 32.0, 'NOx': 25.0, 'NH3': 11.0, 'CO': 0.9, 'SO2': 12.0, 'O3': 32.0},
    "Pune":       {'PM2.5': 58.0,  'PM10': 100.0, 'NO': 13.0, 'NO2': 27.0, 'NOx': 21.0, 'NH3': 9.5,  'CO': 0.75,'SO2': 9.0,  'O3': 38.0},
    "Nagpur":     {'PM2.5': 75.0,  'PM10': 130.0, 'NO': 17.0, 'NO2': 30.0, 'NOx': 24.0, 'NH3': 12.0, 'CO': 0.85,'SO2': 13.0, 'O3': 33.0},
}


def _try_openweather(lat: float, lon: float):
    """
    Returns (partial_result_dict, reason) or (None, reason) on failure.
    Requires lat/lon -- OpenWeather's air pollution endpoint is geo-only,
    there's no name-based lookup.
    """
    api_key = os.environ.get("OPENWEATHER_API_KEY", "").strip().strip('"').strip("'")
    if not api_key or api_key == "your_openweather_api_key_here":
        return None, "no_openweather_key"
    if lat is None or lon is None:
        return None, "no_coordinates_given"

    url = "https://api.openweathermap.org/data/2.5/air_pollution"
    try:
        resp = _get_with_retry(url, params={"lat": lat, "lon": lon, "appid": api_key})
        if resp.status_code == 401:
            return None, "owm_unauthorized (key invalid or not yet activated -- new keys can take a few minutes)"
        if resp.status_code != 200:
            return None, f"owm_http_{resp.status_code}: {resp.text[:200]}"

        payload = resp.json()
        entries = payload.get("list") or []
        if not entries:
            return None, "owm_ok_but_no_data"

        components = entries[0].get("components", {})
        found = {}
        for owm_key, feature in OWM_TO_FEATURE.items():
            if owm_key in components and components[owm_key] is not None:
                found[feature] = round(float(components[owm_key]), 2)

        # Convert CO from ug/m3 (OpenWeather) to mg/m3 (our feature unit).
        if "CO" in found:
            found["CO"] = round(found["CO"] / 1000.0, 3)

        # OpenWeather has no NOx field -- approximate as NO + NO2 when both present.
        if "NO" in found and "NO2" in found:
            found["NOx"] = round(found["NO"] + found["NO2"], 2)

        if not found:
            return None, "owm_ok_but_no_matching_pollutants"

        return found, f"ok ({len(found)} pollutants via OpenWeather Air Pollution API)"

    except requests.exceptions.RequestException as e:
        return None, f"owm_request_error: {e}"
    except Exception as e:
        return None, f"owm_unexpected_error: {e}"


def fetch_live_pollutants(city: str, lat: float = None, lon: float = None) -> dict:
    """
    Returns a dict of all 9 pollutant features (plus "_source" and
    "_reason"). Tries OpenWeather's Air Pollution API by lat/lon, then
    falls back to that city's mock baseline for anything still missing.
    """
    baseline = CITY_MOCK_POLLUTANTS.get(city, DEFAULT_MOCK)
    result = dict(baseline)
    reasons = []
    got_any_live = False

    owm_found, owm_reason = _try_openweather(lat, lon)
    reasons.append(f"openweather: {owm_reason}")
    if owm_found:
        result.update(owm_found)
        got_any_live = True

    result["_source"] = "live" if got_any_live else "mock"
    result["_reason"] = " | ".join(reasons)
    return result
