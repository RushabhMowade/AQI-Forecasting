# AQI Intelligence & Intervention Console

FastAPI backend (retrained XGBoost model + source attribution) + React frontend
(Vite, Tailwind, Recharts). Gives city administrators an accurate current AQI, a
short outlook, source attribution, and a quantified "what would this intervention
actually do" simulator.

## Model card (read this first)

The originally shipped model was trained on data with two serious problems, found
by inspecting `Air_quality_data.csv` and `aqi_dataset.csv` directly:

1. **The provided `AQI` column had ~0 relationship to its own pollutant columns**
   (PM2.5 correlation: -0.0097; day-to-day autocorrelation: -0.004). It doesn't
   appear to be computed from the readings next to it — nothing learnable in it.
2. **`aqi_dataset.csv` (weather/traffic/industrial) has no `City` or `Datetime`
   column at all.** The original notebook joined it with `pd.concat(axis=1)`,
   pairing rows by position — there is no way to join it correctly, because the
   information needed to do so doesn't exist in the file.
3. Every `Datetime` is `00:00:00` — the data is **daily** (2015-2024, 5 cities:
   Delhi, Mumbai, Chennai, Kolkata, Bangalore), not hourly.

**Fix (`backend/../retrain.py` logic, reproduced in `forecast_engine.py`'s
docstring):** compute a real CPCB composite AQI (max of the 7 official pollutant
sub-indices — PM2.5, PM10, NO2, SO2, CO, O3, NH3) directly from the pollutant
columns, and drop the unjoinable weather/traffic/industrial columns entirely
rather than re-fake the pairing.

**Result:**

| | Before | After |
|---|---|---|
| Target | Provided `AQI` column (uncorrelated noise) | Real CPCB composite AQI, computed from pollutants |
| Features | 19, including 5 randomly-paired ones | 9 (just the pollutants) |
| MAE | N/A (target was unlearnable) | **0.78 AQI points** |
| R² | N/A | **99.96%** (held-out) |
| Top features | `traffic_density` importance ≈0.01% | PM2.5 55% + PM10 41% = 97% of the decision |

**What the model does:** accurately maps live pollutant concentrations to AQI.
**What it doesn't do:** predict how AQI changes over time — the source data has
no real temporal signal to learn from (checked: ~0 day-to-day autocorrelation,
flat monthly PM2.5 averages across a full year). The "outlook" in the API is
explicitly *not* a learned forecast — it's the same accurate model re-run per
day on the live reading, adjusted only by real forecast wind speed via a
labeled dispersion heuristic (see `forecast_engine.wind_dispersion_factor`).

## Features

- **Live pollutants**: WAQI (aqicn.org) as the primary source — fast, free,
  covers 586+ real CPCB stations across India. Falls back to data.gov.in's
  own CPCB feed for anything WAQI doesn't report, then to a per-city mock
  baseline if neither is available (see `pollutant_client.py`).
- **Current AQI**: the retrained model's direct output from that reading.
- **Outlook**: multi-day heuristic projection (see model card above).
- **Source attribution + GRAP action plan** (`intervention_engine.py`): ranks
  likely pollution sources (vehicular / industrial / dust / biomass / secondary)
  from pollutant ratios, paired with India's actual Graded Response Action Plan.
- **Intervention simulator** (`/api/scenario`): quantifies a pollutant-load
  reduction (representing the combined effect of traffic curbs, industrial
  curtailment, dust suppression, etc.) against the current baseline before
  a policy is enacted.

## 1. Get API keys (both optional, but strongly recommended)

Without either, pollutant readings are simulated for every city.

**WAQI (primary — do this one, it's fast):**
1. Go to https://aqicn.org/data-platform/token
2. Enter your email — the token is emailed instantly, no account/SSO needed
3. Put it in `backend/.env` as `WAQI_API_TOKEN`

**data.gov.in (secondary/backup — slower, kept for pollutants WAQI misses):**
1. Sign up at https://www.data.gov.in/
2. Log in, go to **Dashboard** (https://www.data.gov.in/dashboard), then **My Account**
3. Put it in `backend/.env` as `DATA_GOV_IN_API_KEY`. Known to be slow/flaky —
   `pollutant_client.py` retries once with a 20s timeout before giving up.

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
Check your API key is working: http://localhost:8000/api/debug/pollutants?city=Delhi

The backend expects `model.json` and `scaler.pkl` next to `main.py` — already included.

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
- `GET /api/forecast?city=Delhi` — current AQI, outlook, pollutants, data source flags
- `GET /api/scenario?city=Delhi&pollutant_reduction_pct=30` — baseline vs. intervention comparison
- `GET /api/interventions?city=Delhi` — source attribution + GRAP action plan
- `GET /api/debug/pollutants?city=Delhi` — diagnose live-feed / API-key issues
- `GET /api/health` — liveness check
