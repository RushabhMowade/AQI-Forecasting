"""Model loading + the 72-hour autoregressive forecast loop."""
import pickle
import numpy as np
import pandas as pd
from xgboost import XGBRegressor

FEATURE_ORDER = [
    'PM2.5', 'PM10', 'NO', 'NO2', 'NOx', 'NH3', 'CO', 'SO2', 'O3',
    'temperature', 'humidity', 'wind_speed', 'traffic_density', 'industrial_activity',
    'AQI_lag_1h', 'AQI_lag_2h', 'AQI_lag_24h', 'Hour_sin', 'Hour_cos'
]

AQI_BANDS = [
    (0, 50, "Good", "#3DDC84"),
    (51, 100, "Satisfactory", "#A8D93E"),
    (101, 200, "Moderate", "#F2C230"),
    (201, 300, "Poor", "#F2914A"),
    (301, 400, "Very Poor", "#E0483C"),
    (401, 500, "Severe", "#8B1E2D"),
]


def aqi_category(value: float):
    for lo, hi, label, color in AQI_BANDS:
        if lo <= value <= hi:
            return label, color
    return ("Severe", "#8B1E2D") if value > 500 else ("Good", "#3DDC84")


# CPCB breakpoint tables for a quick, real sub-index estimate — used only to
# seed the autoregressive lag features with something derived from the actual
# pollutant readings, instead of a fixed made-up starting AQI.
PM25_BREAKPOINTS = [(0, 30, 0, 50), (30, 60, 50, 100), (60, 90, 100, 200),
                    (90, 120, 200, 300), (120, 250, 300, 400), (250, 380, 400, 500)]
PM10_BREAKPOINTS = [(0, 50, 0, 50), (50, 100, 50, 100), (100, 250, 100, 200),
                    (250, 350, 200, 300), (350, 430, 300, 400), (430, 500, 400, 500)]


def _sub_index(conc: float, breakpoints):
    for lo_c, hi_c, lo_i, hi_i in breakpoints:
        if lo_c <= conc <= hi_c:
            return lo_i + (hi_i - lo_i) * (conc - lo_c) / (hi_c - lo_c)
    last = breakpoints[-1]
    return last[3]  # cap at top of scale for anything above the table


def estimate_seed_aqi(live_pollutants: dict) -> float:
    """A rough, real CPCB-style AQI estimate from current PM2.5/PM10, used to
    seed the forecast's lag features instead of a hardcoded constant. Not a
    certified AQI calculation (only 2 of 8 sub-indices), but real and
    city/time-sensitive rather than fixed."""
    pm25_idx = _sub_index(live_pollutants.get('PM2.5', 0), PM25_BREAKPOINTS)
    pm10_idx = _sub_index(live_pollutants.get('PM10', 0), PM10_BREAKPOINTS)
    return max(pm25_idx, pm10_idx)


def load_artifacts(model_json="model.json", model_pkl="model.pkl", scaler_pkl="scaler.pkl"):
    """Prefers the native XGBoost json format (stable across library versions),
    falls back to the pickle."""
    model = XGBRegressor()
    try:
        model.load_model(model_json)
    except Exception:
        with open(model_pkl, "rb") as f:
            model = pickle.load(f)

    with open(scaler_pkl, "rb") as f:
        scaler = pickle.load(f)

    return model, scaler


def run_forecast(model, scaler, live_pollutants: dict, weather_forecast: dict, seed_aqi: float = None):
    """
    Autoregressive 72-hour forecast. Keeps a rolling history of predictions so
    AQI_lag_1h / AQI_lag_2h / AQI_lag_24h are always the real values from
    1h / 2h / 24h before the point being predicted, instead of being frozen.

    seed_aqi seeds that history before hour 0. If not given, it's estimated
    from the actual pollutant readings (see estimate_seed_aqi) so two cities
    with different conditions don't start from the same fictitious baseline.
    """
    if seed_aqi is None:
        seed_aqi = estimate_seed_aqi(live_pollutants)

    history = [seed_aqi - 15.0] * 24 + [seed_aqi - 5.0, seed_aqi]
    predictions = []
    timestamps = weather_forecast["timestamps"]

    for i in range(72):
        ts = pd.to_datetime(timestamps[i])
        hour_sin = np.sin(2 * np.pi * ts.hour / 24.0)
        hour_cos = np.cos(2 * np.pi * ts.hour / 24.0)

        lag_1h, lag_2h, lag_24h = history[-1], history[-2], history[-24]

        feature_dict = {
            'PM2.5': live_pollutants['PM2.5'], 'PM10': live_pollutants['PM10'],
            'NO': live_pollutants['NO'], 'NO2': live_pollutants['NO2'],
            'NOx': live_pollutants['NOx'], 'NH3': live_pollutants['NH3'],
            'CO': live_pollutants['CO'], 'SO2': live_pollutants['SO2'],
            'O3': live_pollutants['O3'],
            'temperature': weather_forecast['temp'][i],
            'humidity': weather_forecast['humidity'][i],
            'wind_speed': weather_forecast['wind'][i],
            'traffic_density': 0.5,
            'industrial_activity': 0.4,
            'AQI_lag_1h': lag_1h,
            'AQI_lag_2h': lag_2h,
            'AQI_lag_24h': lag_24h,
            'Hour_sin': hour_sin,
            'Hour_cos': hour_cos,
        }

        row_df = pd.DataFrame([feature_dict], columns=FEATURE_ORDER)
        row_scaled = scaler.transform(row_df)
        pred_aqi = max(0.0, float(model.predict(row_scaled)[0]))

        predictions.append(pred_aqi)
        history.append(pred_aqi)

    return predictions
