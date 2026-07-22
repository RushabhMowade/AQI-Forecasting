"""
v2 -- retrained on a genuine target. See /home/claude/retrain/retrain.py
(the retraining script) for the full diagnosis and methodology. Summary:

- The original 'AQI' column in Air_quality_data.csv had ~0 correlation with
  its own pollutant columns and ~0 day-to-day autocorrelation -- it wasn't
  learnable. Replaced with a real CPCB composite AQI (max of the 7 official
  pollutant sub-indices) computed directly from PM2.5/PM10/NO2/SO2/CO/O3/NH3.
- aqi_dataset.csv (weather/traffic/industrial) has no City or Datetime
  column, so there's no way to join it correctly -- dropped entirely.
- Calendar features (month, day-of-week) and lag features were tested and
  showed ~0.0000 feature importance -- this dataset has no real seasonal or
  persistence structure (checked: flat monthly means, ~0 autocorrelation).
  Dropped rather than kept as decorative dead weight.

Result: a 9-feature model (just the pollutants) that maps concentrations to
AQI with MAE 0.78 / R^2 99.96% on held-out data -- because that mapping IS
close to a deterministic function (the CPCB formula), and the model learned
it well. PM2.5 + PM10 carry ~97% of the decision.

What this model does NOT do: predict how AQI changes over time. There's no
such signal in the source data. The "outlook" below is explicitly a
heuristic layered on top of live weather forecasts (real, forward-looking
data), not a learned prediction -- and is labeled as such in the API.
"""
import pickle
import pandas as pd
from xgboost import XGBRegressor

FEATURE_ORDER = ['PM2.5', 'PM10', 'NO', 'NO2', 'NOx', 'NH3', 'CO', 'SO2', 'O3']

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


def load_artifacts(model_json="model.json", scaler_pkl="scaler.pkl"):
    model = XGBRegressor()
    model.load_model(model_json)
    with open(scaler_pkl, "rb") as f:
        scaler = pickle.load(f)
    return model, scaler


def predict_aqi(model, scaler, pollutants: dict) -> float:
    """Single-point prediction: pollutant concentrations -> AQI."""
    row = pd.DataFrame([{k: pollutants[k] for k in FEATURE_ORDER}], columns=FEATURE_ORDER)
    scaled = scaler.transform(row)
    return max(0.0, float(model.predict(scaled)[0]))


def wind_dispersion_factor(wind_kmh: float) -> float:
    """Heuristic, NOT learned by the model: higher wind -> better dispersion
    -> lower concentration. ~10 km/h treated as neutral. Used only to shape
    the multi-day outlook from real forecast wind speed, since the model
    itself has no time-dynamics to draw on."""
    factor = 1.25 - 0.03 * wind_kmh
    return max(0.6, min(1.3, factor))


def apply_reduction(pollutants: dict, reduction_pct: float) -> dict:
    """Intervention lever: uniformly scales down pollutant concentrations.
    This is the one lever the model responds strongly to (PM2.5+PM10 are
    ~97% of its decision) -- used by /api/scenario to quantify "what would a
    combined source-reduction effort of X% do to AQI"."""
    mult = 1.0 - max(0.0, min(100.0, reduction_pct)) / 100.0
    return {k: v * mult for k, v in pollutants.items()}


def build_outlook(model, scaler, live_pollutants: dict, daily_wind_kmh: list, reduction_pct: float = 0.0):
    """
    Multi-day outlook. NOT a learned time-series forecast (the model has no
    temporal signal to draw on -- see module docstring) -- each day re-runs
    the real, accurate concentration->AQI model on the live reading adjusted
    by that day's real forecast wind speed via a labeled heuristic, plus any
    intervention reduction. Returns a list of predicted AQI values, one per
    entry in daily_wind_kmh.
    """
    reduced = apply_reduction(live_pollutants, reduction_pct)
    results = []
    for wind in daily_wind_kmh:
        dispersion = wind_dispersion_factor(wind)
        day_pollutants = {k: v * dispersion for k, v in reduced.items()}
        results.append(predict_aqi(model, scaler, day_pollutants))
    return results
