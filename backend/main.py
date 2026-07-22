import os
import concurrent.futures
from pathlib import Path
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from pollutant_client import fetch_live_pollutants
from weather_client import fetch_daily_wind_forecast
from forecast_engine import load_artifacts, predict_aqi, apply_reduction, build_outlook, aqi_category
from intervention_engine import attribute_sources, recommend_actions

# Load .env from next to this file, not whatever directory uvicorn was launched from.
load_dotenv(dotenv_path=Path(__file__).resolve().parent / ".env")

app = FastAPI(title="AQI Intelligence API")

origins = [o.strip() for o in os.environ.get("CORS_ORIGINS", "http://localhost:5173").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def no_cache_headers(request, call_next):
    """These endpoints return live/changing data — never let a browser or
    intermediary cache them by URL."""
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
    return response


try:
    model, scaler = load_artifacts()
except FileNotFoundError as e:
    raise RuntimeError("Missing model.json or scaler.pkl next to main.py") from e

CITIES = {
    "Delhi": {"lat": 28.6139, "lon": 77.2090},
    "Mumbai": {"lat": 19.0760, "lon": 72.8777},
    "Bengaluru": {"lat": 12.9716, "lon": 77.5946},
    "Kolkata": {"lat": 22.5726, "lon": 88.3639},
    "Chennai": {"lat": 13.0827, "lon": 80.2707},
    "Hyderabad": {"lat": 17.3850, "lon": 78.4867},
    "Pune": {"lat": 18.5204, "lon": 73.8567},
    "Nagpur": {"lat": 21.1458, "lon": 79.0882},
}

OUTLOOK_DAYS = 3  # 72-hour outlook


@app.get("/api/cities")
def get_cities():
    return {"cities": list(CITIES.keys())}


@app.get("/api/forecast")
def get_forecast(city: str = Query(..., description="One of /api/cities")):
    """
    Current AQI (from the retrained model: MAE 0.78, R^2 99.96% on held-out
    data — see forecast_engine module docstring) plus a short outlook.

    The outlook is explicitly NOT a learned time-series prediction — the
    training data had no real temporal signal to learn from (see
    forecast_engine docstring) — it's the same accurate model re-run each
    day against the live reading, adjusted only by that day's real forecast
    wind speed via a labeled heuristic (see build_outlook).
    """
    if city not in CITIES:
        raise HTTPException(status_code=400, detail=f"Unknown city '{city}'. See /api/cities.")

    coords = CITIES[city]
    try:
        with concurrent.futures.ThreadPoolExecutor() as executor:
            f_pollutants = executor.submit(fetch_live_pollutants, city, coords["lat"], coords["lon"])
            f_weather = executor.submit(fetch_daily_wind_forecast, coords["lat"], coords["lon"], OUTLOOK_DAYS)
            live_pollutants = f_pollutants.result()
            weather = f_weather.result()

        pollutant_source = live_pollutants.pop("_source", "mock")
        pollutant_reason = live_pollutants.pop("_reason", "")
        reference_aqi = live_pollutants.pop("_reference_aqi", None)

        current_aqi = predict_aqi(model, scaler, live_pollutants)
        outlook_values = build_outlook(model, scaler, live_pollutants, weather["wind"])
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Forecast failed: {e}")

    current_label, current_color = aqi_category(current_aqi)
    peak_value = max(outlook_values)
    peak_day = outlook_values.index(peak_value)
    peak_label, peak_color = aqi_category(peak_value)

    return {
        "city": city,
        "dates": weather["dates"],
        "outlook": [round(v, 1) for v in outlook_values],
        "pollutants": live_pollutants,
        "data_sources": {
            "pollutants": pollutant_source,
            "pollutants_reason": pollutant_reason,
            "weather": weather.get("source", "unknown"),
        },
        # No longer populated (OpenWeather doesn't expose a CPCB-comparable
        # AQI number) -- kept in the response shape for frontend compatibility.
        "reference_aqi": reference_aqi,
        "current": {"value": round(current_aqi, 1), "label": current_label, "color": current_color},
        "peak": {"value": round(peak_value, 1), "label": peak_label, "color": peak_color, "day": peak_day},
    }


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/scenario")
def get_scenario(
    city: str = Query(..., description="One of /api/cities"),
    pollutant_reduction_pct: float = Query(0.0, ge=0.0, le=100.0,
        description="% cut in ambient pollutant concentration, representing the combined real-world effect of source interventions (traffic curbs, industrial curtailment, dust suppression, etc.)."),
):
    """
    Intervention simulator: re-runs the outlook with a pollutant-load
    reduction applied, and returns it side-by-side with the no-intervention
    baseline so an administrator can see the quantified impact of a policy
    before enacting it.
    """
    if city not in CITIES:
        raise HTTPException(status_code=400, detail=f"Unknown city '{city}'. See /api/cities.")

    coords = CITIES[city]
    try:
        with concurrent.futures.ThreadPoolExecutor() as executor:
            f_pollutants = executor.submit(fetch_live_pollutants, city, coords["lat"], coords["lon"])
            f_weather = executor.submit(fetch_daily_wind_forecast, coords["lat"], coords["lon"], OUTLOOK_DAYS)
            live_pollutants = f_pollutants.result()
            weather = f_weather.result()

        live_pollutants.pop("_source", None)
        live_pollutants.pop("_reason", None)
        live_pollutants.pop("_reference_aqi", None)

        baseline = build_outlook(model, scaler, live_pollutants, weather["wind"])
        scenario = build_outlook(model, scaler, live_pollutants, weather["wind"], reduction_pct=pollutant_reduction_pct)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Scenario simulation failed: {e}")

    baseline_peak = max(baseline)
    scenario_peak = max(scenario)
    baseline_mean = sum(baseline) / len(baseline)
    scenario_mean = sum(scenario) / len(scenario)

    return {
        "city": city,
        "dates": weather["dates"],
        "intervention": {"pollutant_reduction_pct": pollutant_reduction_pct},
        "baseline": [round(p, 1) for p in baseline],
        "scenario": [round(p, 1) for p in scenario],
        "impact": {
            "peak_baseline": round(baseline_peak, 1),
            "peak_scenario": round(scenario_peak, 1),
            "peak_reduction": round(baseline_peak - scenario_peak, 1),
            "peak_reduction_pct": round((baseline_peak - scenario_peak) / baseline_peak * 100, 1) if baseline_peak > 0 else 0,
            "mean_baseline": round(baseline_mean, 1),
            "mean_scenario": round(scenario_mean, 1),
            "mean_reduction": round(baseline_mean - scenario_mean, 1),
        },
    }


@app.get("/api/interventions")
def get_interventions(city: str = Query(..., description="One of /api/cities")):
    """
    Source attribution + GRAP-aligned recommended interventions for
    administrators, based on the current live/simulated pollutant snapshot.
    See intervention_engine.py docstring for what this heuristic can and
    can't claim.
    """
    if city not in CITIES:
        raise HTTPException(status_code=400, detail=f"Unknown city '{city}'. See /api/cities.")

    coords = CITIES[city]
    live_pollutants = fetch_live_pollutants(city, coords["lat"], coords["lon"])
    pollutant_source = live_pollutants.pop("_source", "mock")
    pollutant_reason = live_pollutants.pop("_reason", "")
    reference_aqi = live_pollutants.pop("_reference_aqi", None)

    ranked_sources = attribute_sources(live_pollutants)
    current_aqi = predict_aqi(model, scaler, live_pollutants)
    plan = recommend_actions(current_aqi, ranked_sources)

    return {
        "city": city,
        "current_aqi_estimate": round(current_aqi, 1),
        "reference_aqi": reference_aqi,
        "data_source": {"pollutants": pollutant_source, "reason": pollutant_reason},
        "source_attribution": ranked_sources,
        "intervention_plan": plan,
    }


@app.get("/api/debug/pollutants")
def debug_pollutants(city: str = Query(...)):
    """
    Diagnostic endpoint: shows exactly why a city is or isn't using the live
    OpenWeather feed, without going through the forecast pipeline. Hit this
    in a browser or with curl to check your API key setup.
    """
    api_key = os.environ.get("OPENWEATHER_API_KEY", "").strip()
    api_key_present = bool(api_key) and api_key != "your_openweather_api_key_here"
    coords = CITIES.get(city)
    result = fetch_live_pollutants(city, coords["lat"] if coords else None, coords["lon"] if coords else None)
    return {
        "city": city,
        "openweather_key_loaded": api_key_present,
        "source": result.get("_source"),
        "reason": result.get("_reason"),
        "pollutants": {k: v for k, v in result.items() if not k.startswith("_")},
    }
