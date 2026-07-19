"""
Live pollutant readings from the CPCB "Real Time Air Quality Index" feed,
published on data.gov.in.

Resource: https://www.data.gov.in/resource/real-time-air-quality-index-various-locations
Resource ID: 3b01bcb8-0b14-4abf-b6f2-c1bfd384ba69

Getting an API key (free):
  1. Sign up at https://www.data.gov.in/
  2. Go to "My Account" -> "API Key"
  3. Put it in backend/.env as DATA_GOV_IN_API_KEY

Without a key (or if the request fails / the city has no live stations right now),
this falls back to representative mock values so the app never breaks.
"""
import os
import requests

RESOURCE_URL = "https://api.data.gov.in/resource/3b01bcb8-0b14-4abf-b6f2-c1bfd384ba69"

# CPCB pollutant_id strings -> the feature names our model was trained on
CPCB_TO_FEATURE = {
    "PM2.5": "PM2.5",
    "PM10": "PM10",
    "NO2": "NO2",
    "NO": "NO",
    "NOX": "NOx",
    "NH3": "NH3",
    "CO": "CO",
    "SO2": "SO2",
    "OZONE": "O3",
}

# Representative fallback values (used for any pollutant the live feed doesn't
# report for a given city, or if the whole request fails / no key is set).
MOCK_POLLUTANTS = {
    'PM2.5': 65.0, 'PM10': 110.0, 'NO': 15.2, 'NO2': 28.4,
    'NOx': 22.1, 'NH3': 12.5, 'CO': 0.9, 'SO2': 14.3, 'O3': 38.0
}


def fetch_live_pollutants(city: str) -> dict:
    """
    Returns a dict of all 9 pollutant features. Real CPCB station readings
    (averaged across stations in the city) are used wherever available;
    any pollutant missing from the live feed is filled in from MOCK_POLLUTANTS
    so the model always receives a complete, valid feature vector.
    """
    api_key = os.environ.get("DATA_GOV_IN_API_KEY", "").strip()
    result = dict(MOCK_POLLUTANTS)
    result["_source"] = "mock"

    if not api_key:
        return result

    try:
        resp = requests.get(
            RESOURCE_URL,
            params={
                "api-key": api_key,
                "format": "json",
                "limit": 1000,
                "filters[city]": city,
            },
            timeout=6,
        )
        resp.raise_for_status()
        records = resp.json().get("records", [])

        if not records:
            return result  # no live stations for this city right now -> pure mock

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

        live_found = False
        for feature, total in sums.items():
            result[feature] = round(total / counts[feature], 2)
            live_found = True

        result["_source"] = "live" if live_found else "mock"
        return result

    except Exception:
        # Network error, bad key, rate limit, etc. -> safe fallback, app keeps working.
        return result
