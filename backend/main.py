import os
import concurrent.futures
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from pollutant_client import fetch_live_pollutants
from weather_client import fetch_weather_forecast
from forecast_engine import load_artifacts, run_forecast, aqi_category

load_dotenv()

app = FastAPI(title="Hyperlocal AQI Forecast API")

origins = [o.strip() for o in os.environ.get("CORS_ORIGINS", "http://localhost:5173").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

try:
    model, scaler = load_artifacts()
except FileNotFoundError as e:
    raise RuntimeError(
        "Missing model.json/model.pkl or scaler.pkl next to main.py"
    ) from e

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


@app.get("/api/cities")
def get_cities():
    return {"cities": list(CITIES.keys())}


@app.get("/api/forecast")
def get_forecast(city: str = Query(..., description="One of /api/cities")):
    if city not in CITIES:
        raise HTTPException(status_code=400, detail=f"Unknown city '{city}'. See /api/cities.")

    coords = CITIES[city]

    try:
        with concurrent.futures.ThreadPoolExecutor() as executor:
            f_pollutants = executor.submit(fetch_live_pollutants, city)
            f_weather = executor.submit(fetch_weather_forecast, coords["lat"], coords["lon"])
            live_pollutants = f_pollutants.result()
            weather_forecast = f_weather.result()

        pollutant_source = live_pollutants.pop("_source", "mock")
        predictions = run_forecast(model, scaler, live_pollutants, weather_forecast)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Forecast failed: {e}")

    current_label, current_color = aqi_category(predictions[0])
    peak_value = max(predictions)
    peak_hour = predictions.index(peak_value)
    peak_label, peak_color = aqi_category(peak_value)

    return {
        "city": city,
        "timestamps": weather_forecast["timestamps"],
        "predictions": [round(p, 1) for p in predictions],
        "pollutants": live_pollutants,
        "data_sources": {"pollutants": pollutant_source, "weather": weather_forecast.get("source", "unknown")},
        "current": {"value": round(predictions[0], 1), "label": current_label, "color": current_color},
        "peak": {"value": round(peak_value, 1), "label": peak_label, "color": peak_color, "hour": peak_hour},
    }


@app.get("/api/health")
def health():
    return {"status": "ok"}
