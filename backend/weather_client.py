"""Daily wind-speed forecast from Open-Meteo (no key required), used only to
shape the multi-day AQI outlook heuristic (see forecast_engine.build_outlook).
Falls back to a flat neutral assumption if the request fails."""
import datetime
import requests


def fetch_daily_wind_forecast(lat: float, lon: float, days: int = 4) -> dict:
    url = "https://api.open-meteo.com/v1/forecast"
    try:
        res = requests.get(
            url,
            params={
                "latitude": lat,
                "longitude": lon,
                "daily": "wind_speed_10m_max",
                "forecast_days": days,
                "timezone": "auto",
            },
            timeout=6,
        ).json()
        daily = res["daily"]
        dates = daily["time"][:days]
        wind = daily["wind_speed_10m_max"][:days]
        if len(dates) < days:
            raise ValueError("Incomplete forecast payload")
        return {"dates": dates, "wind": wind, "source": "live"}
    except Exception:
        today = datetime.date.today()
        dates = [(today + datetime.timedelta(days=i)).isoformat() for i in range(days)]
        return {"dates": dates, "wind": [10.0] * days, "source": "synthetic"}
