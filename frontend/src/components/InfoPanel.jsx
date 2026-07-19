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
            Pollutants: <span className="font-mono text-xs">{sources?.pollutants === 'live' ? 'live CPCB stations via data.gov.in' : 'simulated (no live station data returned for this city, or no API key configured)'}</span>
          </p>
          <p>
            Weather: <span className="font-mono text-xs">{sources?.weather === 'live' ? 'live Open-Meteo forecast' : 'synthetic seasonal curve (Open-Meteo request failed)'}</span>
          </p>
          <p>
            traffic_density and industrial_activity are fixed placeholders (0.5 / 0.4) — no live feed exists for them yet.
          </p>
          <p>
            The forecast is autoregressive: each hour's prediction feeds the 1h / 2h / 24h lag features for later hours, so early errors can compound over the 72-hour window.
          </p>
        </div>
      )}
    </div>
  )
}
