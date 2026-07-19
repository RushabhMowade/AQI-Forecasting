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

# Representative fallback values, per city, used when no live reading is
# available (no API key, no live station for that pollutant/city, or the
# request fails). These are NOT live data — just rough, city-typical
# profiles so the demo doesn't collapse to one identical number everywhere.
# Swap in a real key and these are only ever used as a per-pollutant patch.
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


def fetch_live_pollutants(city: str) -> dict:
    """
    Returns a dict of all 9 pollutant features. Real CPCB station readings
    (averaged across stations in the city) are used wherever available;
    any pollutant missing from the live feed is filled in from that city's
    mock baseline so the model always receives a complete, valid feature vector.

    result["_source"] is "live" or "mock".
    result["_reason"] explains *why* if it's "mock" (no_key / http_error / no_records / request_error / etc.)
    so a misconfigured key doesn't fail silently.
    """
    api_key = os.environ.get("DATA_GOV_IN_API_KEY", "").strip().strip('"').strip("'")
    baseline = CITY_MOCK_POLLUTANTS.get(city, DEFAULT_MOCK)
    result = dict(baseline)
    result["_source"] = "mock"

    if not api_key:
        result["_reason"] = "no_key"
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

        if resp.status_code != 200:
            result["_reason"] = f"http_{resp.status_code}: {resp.text[:200]}"
            return result

        payload = resp.json()
        records = payload.get("records", [])

        if not records:
            # Try again without the city filter so we can tell "wrong city
            # spelling" apart from "genuinely no live stations right now".
            probe = requests.get(
                RESOURCE_URL,
                params={"api-key": api_key, "format": "json", "limit": 1},
                timeout=6,
            )
            if probe.status_code == 200 and probe.json().get("records"):
                result["_reason"] = f"no_records_for_city '{city}' (key works, but this city isn't in the feed right now or the name doesn't match CPCB's spelling)"
            else:
                result["_reason"] = f"no_records_at_all (key likely invalid or unauthorized: {probe.status_code})"
            return result

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
            result["_reason"] = f"records_found_but_unparseable ({len(records)} records, none matched known pollutant_id values)"
            return result

        for feature, total in sums.items():
            result[feature] = round(total / counts[feature], 2)

        result["_source"] = "live"
        result["_reason"] = f"ok ({len(records)} station readings)"
        return result

    except requests.exceptions.RequestException as e:
        result["_reason"] = f"request_error: {e}"
        return result
    except Exception as e:
        result["_reason"] = f"unexpected_error: {e}"
        return result
