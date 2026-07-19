# Hyperlocal AQI Forecast Dashboard

A FastAPI backend (serving the XGBoost AQI model) + React frontend (Vite, Tailwind, Recharts),
replacing the previous single-file Streamlit app.

- **Live pollutants**: pulled from CPCB's real-time feed on data.gov.in when an API key is
  configured; falls back to representative mock values per-pollutant if a reading isn't
  available (missing key, no live station for that city, request failure).
- **Live weather**: pulled from Open-Meteo (no key needed); falls back to a synthetic
  seasonal curve if the request fails.
- **Forecast**: same trained XGBoost model as before, with the autoregressive lag bug fixed —
  `AQI_lag_24h` now tracks the real prediction from 24 hours prior instead of staying frozen.

## 1. Get a data.gov.in API key (optional but recommended)

Without this, pollutant readings are simulated for every city.

1. Sign up at https://www.data.gov.in/
2. Go to **My Account -> API Key**
3. Copy the key

## 2. Run the backend

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate   # optional but recommended
pip install -r requirements.txt
cp .env.example .env
# edit .env and paste your DATA_GOV_IN_API_KEY (optional)
uvicorn main:app --reload --port 8000
```

Check it's alive: http://localhost:8000/api/health

The backend expects `model.json` (or `model.pkl`) and `scaler.pkl` to sit next to `main.py` —
they're already included in this folder.

## 3. Run the frontend

```bash
cd frontend
npm install
cp .env.example .env      # only needed if your backend isn't on localhost:8000
npm run dev
```

Open http://localhost:5173, pick a city, and click **Generate forecast**.

## API reference

- `GET /api/cities` — list of supported cities
- `GET /api/forecast?city=Delhi` — pollutants, 72-hour predictions, AQI category, data source flags
- `GET /api/health` — liveness check

## What's simulated vs. live

| Signal | Source | Fallback |
|---|---|---|
| Pollutants (PM2.5, PM10, NO, NO2, NOx, NH3, CO, SO2, O3) | CPCB via data.gov.in | Mock values, per-pollutant |
| Weather (temp, humidity, wind) | Open-Meteo | Synthetic seasonal curve |
| `traffic_density`, `industrial_activity` | — | Fixed placeholders (0.5 / 0.4) — no live feed exists for these yet |

Each `/api/forecast` response includes a `data_sources` field so the UI can show which parts
of the current forecast are real vs. simulated — check it in the "About this forecast" panel
in the app.

## Known limitation

Pollutant readings are fetched once per forecast run and held constant across the full 72-hour
window (CPCB's feed is current-conditions, not a 3-day pollutant forecast). Combined with fixed
traffic/industrial placeholders, this means the model leans heavily on the (slowly changing)
weather and time-of-day features for hour-to-hour movement — the curve can look flatter than a
true forecast would with hourly-varying pollutant inputs.
