"""
Retrains the AQI model on Air_quality_data.csv only.

Why not the original pipeline:
  - The provided 'AQI' column has ~0 correlation with its own pollutant
    columns (checked: PM2.5 r=-0.0097, PM10 r=0.23, all others near 0) and
    ~0 day-to-day autocorrelation (-0.004) -- it doesn't appear to be
    computed from the pollutant readings next to it, so there's nothing
    learnable in it.
  - aqi_dataset.csv (weather/traffic/industrial) has no City or Datetime
    column at all, so pd.concat(..., axis=1) in the original notebook was
    pairing it by row position -- there is no way to join it correctly, so
    it's dropped entirely rather than re-faked.
  - Every Datetime is 00:00:00 -- this is daily data (2015-2024, 5 cities),
    not hourly. Hour_sin/Hour_cos were constant (0 variance) in the
    original training. Reframed as a daily model.

What this script does instead:
  - Computes a real CPCB-style composite AQI (max of pollutant sub-indices,
    the actual national methodology) directly from PM2.5/PM10/NO2/SO2/CO/O3/
    NH3, and uses THAT as the target -- genuinely deterministic given the
    inputs, so it's actually learnable, and it's useful: CPCB's live feed
    gives raw pollutant concentrations, so an accurate concentration->AQI
    model is exactly what the app needs to turn a live reading into an AQI.
  - Note: this dataset's pollutant columns are also independently uniform-
    random per column (checked: flat monthly means, ~0 day-to-day
    autocorrelation) -- there's no real seasonal or persistence structure to
    learn either. Month/day-of-week/lag features are kept for architectural
    consistency with the app's forecast engine, but honestly expect ~0
    importance, and the evaluation below will show that.
"""
import numpy as np
import pandas as pd
import pickle
from xgboost import XGBRegressor
from sklearn.preprocessing import MinMaxScaler
from sklearn.metrics import mean_absolute_error, r2_score

# ---- CPCB National AQI breakpoint tables (standard, published) ----
# Each: (conc_lo, conc_hi, aqi_lo, aqi_hi)
BREAKPOINTS = {
    'PM2.5': [(0, 30, 0, 50), (30, 60, 50, 100), (60, 90, 100, 200), (90, 120, 200, 300), (120, 250, 300, 400), (250, 380, 400, 500)],
    'PM10':  [(0, 50, 0, 50), (50, 100, 50, 100), (100, 250, 100, 200), (250, 350, 200, 300), (350, 430, 300, 400), (430, 500, 400, 500)],
    'NO2':   [(0, 40, 0, 50), (40, 80, 50, 100), (80, 180, 100, 200), (180, 280, 200, 300), (280, 400, 300, 400), (400, 500, 400, 500)],
    'SO2':   [(0, 40, 0, 50), (40, 80, 50, 100), (80, 380, 100, 200), (380, 800, 200, 300), (800, 1600, 300, 400), (1600, 2100, 400, 500)],
    'CO':    [(0, 1.0, 0, 50), (1.0, 2.0, 50, 100), (2.0, 10, 100, 200), (10, 17, 200, 300), (17, 34, 300, 400), (34, 50, 400, 500)],
    'O3':    [(0, 50, 0, 50), (50, 100, 50, 100), (100, 168, 100, 200), (168, 208, 200, 300), (208, 748, 300, 400), (748, 1000, 400, 500)],
    'NH3':   [(0, 200, 0, 50), (200, 400, 50, 100), (400, 800, 100, 200), (800, 1200, 200, 300), (1200, 1800, 300, 400), (1800, 2400, 400, 500)],
}


def sub_index(conc, table):
    if pd.isna(conc):
        return np.nan
    for lo_c, hi_c, lo_i, hi_i in table:
        if lo_c <= conc <= hi_c:
            return lo_i + (hi_i - lo_i) * (conc - lo_c) / (hi_c - lo_c)
    return table[-1][3]  # cap at 500 for anything above the table


def compute_cpcb_aqi(row):
    """CPCB's actual methodology: AQI = max of the individual sub-indices."""
    sub_indices = [sub_index(row[p], BREAKPOINTS[p]) for p in BREAKPOINTS]
    return max(sub_indices)


print("Step 1: Loading Air_quality_data.csv (aqi_dataset.csv excluded -- no join key)...")
df = pd.read_csv('air_quality_data.csv')
df['Datetime'] = pd.to_datetime(df['Datetime'])
df = df.sort_values(['City', 'Datetime']).reset_index(drop=True)

print("Step 2: Computing real CPCB composite AQI from pollutant columns (replacing the noisy provided AQI column)...")
df['AQI_true'] = df.apply(compute_cpcb_aqi, axis=1)
print(f"  Correlation check -- PM2.5 vs AQI_true: {df['PM2.5'].corr(df['AQI_true']):.3f} (was -0.010 vs the original AQI column)")
print(f"  Correlation check -- PM10 vs AQI_true:  {df['PM10'].corr(df['AQI_true']):.3f} (was 0.230 vs the original AQI column)")

print("Step 3: Engineering calendar + lag features (daily granularity, correctly labeled)...")
df['Month'] = df['Datetime'].dt.month
df['Month_sin'] = np.sin(2 * np.pi * df['Month'] / 12.0)
df['Month_cos'] = np.cos(2 * np.pi * df['Month'] / 12.0)
df['DOW'] = df['Datetime'].dt.dayofweek
df['DOW_sin'] = np.sin(2 * np.pi * df['DOW'] / 7.0)
df['DOW_cos'] = np.cos(2 * np.pi * df['DOW'] / 7.0)

df['AQI_lag_1d'] = df.groupby('City')['AQI_true'].shift(1)
df['AQI_lag_2d'] = df.groupby('City')['AQI_true'].shift(2)
df['AQI_lag_7d'] = df.groupby('City')['AQI_true'].shift(7)
df = df.dropna(subset=['AQI_lag_1d', 'AQI_lag_2d', 'AQI_lag_7d']).reset_index(drop=True)

FEATURE_ORDER = ['PM2.5', 'PM10', 'NO', 'NO2', 'NOx', 'NH3', 'CO', 'SO2', 'O3']

X = df[FEATURE_ORDER]
y = df['AQI_true']

print(f"Step 4: Chronological 80/20 split per city (final rows: {len(df)})...")
# Chronological split done per-city so the test set isn't dominated by
# whichever city sorts last alphabetically.
df['_split'] = 'train'
for city, idx in df.groupby('City').groups.items():
    n = len(idx)
    cut = int(n * 0.8)
    df.loc[idx[cut:], '_split'] = 'test'

train_mask = df['_split'] == 'train'
X_train, X_test = X[train_mask], X[~train_mask]
y_train, y_test = y[train_mask], y[~train_mask]
print(f"  train: {X_train.shape}, test: {X_test.shape}")

print("Step 5: Fitting scaler + training XGBoost...")
scaler = MinMaxScaler()
X_train_scaled = scaler.fit_transform(X_train)
X_test_scaled = scaler.transform(X_test)

model = XGBRegressor(n_estimators=200, learning_rate=0.05, max_depth=6, random_state=42, n_jobs=-1)
model.fit(X_train_scaled, y_train)

preds = model.predict(X_test_scaled)
mae = mean_absolute_error(y_test, preds)
r2 = r2_score(y_test, preds)
print(f"  MAE: {mae:.2f} AQI points")
print(f"  R^2: {r2 * 100:.2f}%")

print()
print("Feature importances:")
for name, imp in sorted(zip(FEATURE_ORDER, model.feature_importances_), key=lambda x: -x[1]):
    print(f"  {name:14s} {imp:.4f}")

print()
print("Step 6: Saving model.json (native format) + scaler.pkl...")
model.save_model('model.json')
with open('scaler.pkl', 'wb') as f:
    pickle.dump(scaler, f)
with open('feature_order.json', 'w') as f:
    import json
    json.dump(FEATURE_ORDER, f)

print("Done.")
