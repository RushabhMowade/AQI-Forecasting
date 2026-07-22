"""
Live pollutant readings, tried in this order:

  1. WAQI (World Air Quality Index / aqicn.org) — fast, free, instant token,
     aggregates 586+ real CPCB stations across India (explicitly attributed
     to "CPCB - India Central Pollution Control Board" in its own API
     responses). Get a token in seconds at https://aqicn.org/data-platform/token
     (just an email, no government SSO). Put it in backend/.env as
     WAQI_API_TOKEN.

  2. data.gov.in's own "Real Time Air Quality Index" feed — kept as a
     secondary source since it's the original CPCB dataset directly, but
     it's known to be slow/flaky (see the retry logic below). Needs
     DATA_GOV_IN_API_KEY in backend/.env.

  3. Per-city mock baseline — used if neither of the above returns usable
     data, so the app never breaks.

IMPORTANT UNIT NOTE: WAQI reports each pollutant as an already-computed AQI
sub-index (0-500 scale), not a raw µg/m³ concentration — confirmed by their
own sample responses, where e.g. iaqi.pm25.v exactly equals the overall aqi
value when PM2.5 is the dominant pollutant. Our model needs raw
concentrations, so WAQI's sub-index values are inverted back through the
same CPCB breakpoint table (result: an approximate concentration, not a
measured one) to keep them compatible with the rest of the pipeline. When
WAQI succeeds, we also keep its own official `aqi` number as
`reference_aqi` in the result — a ground-truth number you can compare our
model's estimate against directly, instead of guessing.
"""
import os
import time
import requests

# ---- CPCB breakpoint tables (same methodology as forecast_engine/retrain.py) ----
BREAKPOINTS = {
    'PM2.5': [(0, 30, 0, 50), (30, 60, 50, 100), (60, 90, 100, 200), (90, 120, 200, 300), (120, 250, 300, 400), (250, 380, 400, 500)],
    'PM10':  [(0, 50, 0, 50), (50, 100, 50, 100), (100, 250, 100, 200), (250, 350, 200, 300), (350, 430, 300, 400), (430, 500, 400, 500)],
    'NO2':   [(0, 40, 0, 50), (40, 80, 50, 100), (80, 180, 100, 200), (180, 280, 200, 300), (280, 400, 300, 400), (400, 500, 400, 500)],
    'SO2':   [(0, 40, 0, 50), (40, 80, 50, 100), (80, 380, 100, 200), (380, 800, 200, 300), (800, 1600, 300, 400), (1600, 2100, 400, 500)],
    'CO':    [(0, 1.0, 0, 50), (1.0, 2.0, 50, 100), (2.0, 10, 100, 200), (10, 17, 200, 300), (17, 34, 300, 400), (34, 50, 400, 500)],
    'O3':    [(0, 50, 0, 50), (50, 100, 50, 100), (100, 168, 100, 200), (168, 208, 200, 300), (208, 748, 300, 400), (748, 1000, 400, 500)],
}


def _index_to_concentration(sub_index: float, table) -> float:
    """Inverse of the CPCB breakpoint formula: given a 0-500 sub-index,
    return the concentration at the midpoint of the matching segment.
    Approximate by construction (a whole segment collapses to one point)."""
    for lo_c, hi_c, lo_i, hi_i in table:
        if lo_i <= sub_index <= hi_i:
            frac = (sub_index - lo_i) / (hi_i - lo_i) if hi_i > lo_i else 0.5
            return lo_c + frac * (hi_c - lo_c)
    return table[-1][1]  # cap at top of table's concentration range


# data.gov.in's API is known to be slow (not down) — a short timeout reads as
# a hard failure when it's really just latency. Retry a couple of times with
# a generous timeout before giving up.
REQUEST_TIMEOUT = 20
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


# CPCB pollutant_id strings (data.gov.in feed) -> our feature names
CPCB_TO_FEATURE = {
    "PM2.5": "PM2.5", "PM10": "PM10", "NO2": "NO2", "NO": "NO",
    "NOX": "NOx", "NH3": "NH3", "CO": "CO", "SO2": "SO2", "OZONE": "O3",
}

# WAQI iaqi keys -> our feature names. WAQI doesn't report NH3/NO/NOx for
# almost any Indian station, so those three always come from the mock
# baseline even on a WAQI "live" hit.
WAQI_TO_FEATURE = {
    "pm25": "PM2.5", "pm10": "PM10", "no2": "NO2",
    "so2": "SO2", "co": "CO", "o3": "O3",
}

# Representative fallback values, per city — NOT live data, just rough
# city-typical profiles so the demo doesn't collapse to one identical number
# everywhere when no live source is available. Also fills in any pollutant a
# live source doesn't report (e.g. NH3/NO/NOx from WAQI).
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


def _try_waqi(city: str, lat: float = None, lon: float = None):
    """
    Returns (partial_result_dict, reference_aqi, reason) or (None, None, reason).

    Prefers WAQI's geo lookup (nearest real station to lat/lon) over its
    plain-name search — name-based /feed/{city}/ only reliably resolves a
    handful of famous cities (Delhi matches exactly); for others it can match
    a station or placeholder with no pollutant data at all, which is exactly
    what "waqi_ok_but_no_matching_pollutants" means. Falls back to name-based
    lookup only if no coordinates were given.
    """
    token = os.environ.get("WAQI_API_TOKEN", "").strip().strip('"').strip("'")
    if not token:
        return None, None, "no_waqi_token"

    if lat is not None and lon is not None:
        url = f"https://api.waqi.info/feed/geo:{lat};{lon}/"
    else:
        url = f"https://api.waqi.info/feed/{city}/"

    try:
        resp = _get_with_retry(url, params={"token": token}, timeout=8)
        if resp.status_code != 200:
            return None, None, f"waqi_http_{resp.status_code}"

        payload = resp.json()
        if payload.get("status") != "ok":
            return None, None, f"waqi_status_{payload.get('status')}: {payload.get('data')}"

        data = payload["data"]
        iaqi = data.get("iaqi", {})
        found = {}
        for waqi_key, feature in WAQI_TO_FEATURE.items():
            if waqi_key in iaqi and "v" in iaqi[waqi_key]:
                sub_index = float(iaqi[waqi_key]["v"])
                found[feature] = round(_index_to_concentration(sub_index, BREAKPOINTS[feature]), 2)

        if not found:
            if lat is not None and lon is not None:
                # Geo lookup resolved to something, but it had no pollutant
                # data (e.g. a met-only station). Try name-based as a
                # second attempt before giving up entirely.
                try:
                    resp2 = _get_with_retry(f"https://api.waqi.info/feed/{city}/", params={"token": token}, timeout=8)
                    if resp2.status_code == 200 and resp2.json().get("status") == "ok":
                        data2 = resp2.json()["data"]
                        iaqi2 = data2.get("iaqi", {})
                        found2 = {}
                        for waqi_key, feature in WAQI_TO_FEATURE.items():
                            if waqi_key in iaqi2 and "v" in iaqi2[waqi_key]:
                                found2[feature] = round(_index_to_concentration(float(iaqi2[waqi_key]["v"]), BREAKPOINTS[feature]), 2)
                        if found2:
                            ref2 = data2.get("aqi")
                            station2 = data2.get("city", {}).get("name", city)
                            return found2, ref2, f"ok ({len(found2)} pollutants via WAQI name-lookup fallback, station: {station2})"
                except requests.exceptions.RequestException:
                    pass
            return None, None, "waqi_ok_but_no_matching_pollutants (nearest station has no live pollutant data)"

        reference_aqi = data.get("aqi")
        station = data.get("city", {}).get("name", city)
        return found, reference_aqi, f"ok ({len(found)} pollutants via WAQI, station: {station})"

    except requests.exceptions.RequestException as e:
        return None, None, f"waqi_request_error: {e}"
    except Exception as e:
        return None, None, f"waqi_unexpected_error: {e}"


def _try_data_gov_in(city: str):
    """Returns (partial_result_dict, reason) or (None, reason) on failure."""
    api_key = os.environ.get("DATA_GOV_IN_API_KEY", "").strip().strip('"').strip("'")
    if not api_key:
        return None, "no_data_gov_in_key"

    resource_url = "https://api.data.gov.in/resource/3b01bcb8-0b14-4abf-b6f2-c1bfd384ba69"
    try:
        resp = _get_with_retry(resource_url, params={
            "api-key": api_key, "format": "json", "limit": 1000, "filters[city]": city,
        })
        if resp.status_code != 200:
            return None, f"http_{resp.status_code}: {resp.text[:200]}"

        records = resp.json().get("records", [])
        if not records:
            return None, f"no_records_for_city '{city}'"

        sums, counts = {}, {}
        for r in records:
            pid = (r.get("pollutant_id") or "").upper().strip()
            feature = CPCB_TO_FEATURE.get(pid)
            if not feature:
                continue
            try:
                val = float(r.get("pollutant_avg") or r.get("pollutant_min") or r.get("pollutant_max"))
            except (TypeError, ValueError):
                continue
            sums[feature] = sums.get(feature, 0.0) + val
            counts[feature] = counts.get(feature, 0) + 1

        if not sums:
            return None, f"records_found_but_unparseable ({len(records)} records)"

        found = {feature: round(total / counts[feature], 2) for feature, total in sums.items()}
        return found, f"ok ({len(records)} station readings)"

    except requests.exceptions.RequestException as e:
        return None, f"request_error: {e}"
    except Exception as e:
        return None, f"unexpected_error: {e}"


def fetch_live_pollutants(city: str, lat: float = None, lon: float = None) -> dict:
    """
    Returns a dict of all 9 pollutant features (plus "_source", "_reason",
    and "_reference_aqi" when available). Tries WAQI (geo lookup by
    lat/lon if given — much more reliable than name search for anything
    but a handful of famous cities), then data.gov.in, then falls back to
    that city's mock baseline for anything still missing.
    """
    baseline = CITY_MOCK_POLLUTANTS.get(city, DEFAULT_MOCK)
    result = dict(baseline)
    reasons = []
    reference_aqi = None
    got_any_live = False

    waqi_found, waqi_ref, waqi_reason = _try_waqi(city, lat, lon)
    reasons.append(f"waqi: {waqi_reason}")
    if waqi_found:
        result.update(waqi_found)
        reference_aqi = waqi_ref
        got_any_live = True

    # Only fall through to data.gov.in for pollutants WAQI didn't cover
    # (or if WAQI failed outright) — no point hammering a slow API for
    # data we already have.
    still_missing = set(DEFAULT_MOCK) - set(waqi_found or {})
    if still_missing:
        dgi_found, dgi_reason = _try_data_gov_in(city)
        reasons.append(f"data.gov.in: {dgi_reason}")
        if dgi_found:
            result.update({k: v for k, v in dgi_found.items() if k in still_missing or k not in (waqi_found or {})})
            got_any_live = True

    result["_source"] = "live" if got_any_live else "mock"
    result["_reason"] = " | ".join(reasons)
    if reference_aqi is not None:
        result["_reference_aqi"] = reference_aqi
    return result
