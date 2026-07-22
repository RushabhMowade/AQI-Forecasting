# Model retraining

Reproduces `backend/model.json` + `backend/scaler.pkl`. See the model card in
the top-level README for why this was necessary and what changed.

```bash
pip install pandas numpy xgboost scikit-learn
# Air_quality_data.csv must be in this folder (not included here - bring your own copy)
python3 retrain.py
```

Outputs `model.json`, `scaler.pkl`, `feature_order.json` — copy `model.json`
and `scaler.pkl` into `backend/` to deploy.

Note: `aqi_dataset.csv` (the original weather/traffic/industrial file) is
intentionally not used — it has no City/Datetime column, so there's no valid
way to join it to the pollutant data. See the top-level README for details.
