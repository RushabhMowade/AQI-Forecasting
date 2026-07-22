import { useState } from 'react'

export default function InfoPanel({ sources }) {
  const [open, setOpen] = useState(false)
  return (
    <div className="border border-hairline rounded-lg overflow-hidden">
      <button
        onClick={() => setOpen(!open)}
        className="w-full text-left px-4 py-3 text-sm text-muted flex items-center justify-between"
      >
        About this forecast
        <span className="text-xs">{open ? '−' : '+'}</span>
      </button>
      {open && (
        <div className="px-4 pb-4 text-sm text-muted space-y-2">
          <p>
            Pollutants: <span className="font-mono text-xs">{sources?.pollutants === 'live' ? 'live (WAQI/CPCB, with data.gov.in as backup)' : 'simulated'}</span>
            {sources?.pollutants !== 'live' && sources?.pollutants_reason && (
              <span className="block text-xs text-band-poor mt-1">Reason: {sources.pollutants_reason}</span>
            )}
          </p>
          <p>
            When available, the "Official reading" badge next to the gauge is WAQI's own published AQI for that
            city — a ground-truth number to compare our model's estimate against directly. WAQI reports pollutants
            as pre-computed sub-indices rather than raw concentrations, so those are converted back to an
            approximate concentration (inverse of the CPCB breakpoint formula) before being fed to our model —
            expect a small amount of rounding between the two numbers even when both are "live".
          </p>
          <p>
            Weather (used only to shape the outlook, see below): <span className="font-mono text-xs">{sources?.weather === 'live' ? 'live Open-Meteo forecast' : 'synthetic fallback (Open-Meteo request failed)'}</span>
          </p>
          <p>
            <span className="text-ink">The model was retrained</span> after the original training data was found to
            be unreliable: the provided AQI column had ~0 correlation with its own pollutant columns, and the
            separate weather/traffic/industrial file had no city or date to join on at all. Fixed by computing a
            real CPCB composite AQI (max of the 7 official pollutant sub-indices) directly from PM2.5/PM10/NO2/SO2/
            CO/O3/NH3, and dropping the unjoinable weather/traffic/industrial columns entirely rather than re-faking
            the pairing. Result: MAE 0.78 AQI points, R² 99.96% on held-out data — PM2.5 + PM10 carry ~97% of the
            model's decision.
          </p>
          <p>
            <span className="text-ink">What the outlook is (and isn't):</span> the source data has no real day-to-day
            trend to learn from (checked: ~0 autocorrelation, flat monthly averages) — so the "outlook" above is the
            same accurate model re-run each day on the live reading, adjusted only by that day's real forecast wind
            speed via a labeled dispersion heuristic. It is not a learned time-series prediction.
          </p>
        </div>
      )}
    </div>
  )
}
