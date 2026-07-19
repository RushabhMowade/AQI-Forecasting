"""72-hour weather forecast from Open-Meteo (no key required), with a
synthetic seasonal fallback if the request fails."""
import datetime
import requests


def fetch_weather_forecast(lat: float, lon: float) -> dict:
    url = "https://api.open-meteo.com/v1/forecast"
    try:
        res = requests.get(
            url,
            params={
                "latitude": lat,
                "longitude": lon,
                "hourly": "temperature_2m,relative_humidity_2m,wind_speed_10m",
                "forecast_days": 3,
            },
            timeout=6,
        ).json()
        hourly = res["hourly"]
        timestamps = hourly["time"][:72]
        temp = hourly["temperature_2m"][:72]
        humidity = hourly["relative_humidity_2m"][:72]
        wind = hourly["wind_speed_10m"][:72]
        if len(timestamps) < 72:
            raise ValueError("Incomplete forecast payload")
        return {"timestamps": timestamps, "temp": temp, "humidity": humidity, "wind": wind, "source": "live"}
    except Exception:
        now = datetime.datetime.now().replace(minute=0, second=0, microsecond=0)
        timestamps = [(now + datetime.timedelta(hours=i)).isoformat() for i in range(72)]
        import math
        return {
            "timestamps": timestamps,
            "temp": [28.0 + 4 * math.sin(i / 6) for i in range(72)],
            "humidity": [60.0 + 10 * math.cos(i / 6) for i in range(72)],
            "wind": [12.0 + 3 * math.sin(i / 12) for i in range(72)],
            "source": "synthetic",
        }
