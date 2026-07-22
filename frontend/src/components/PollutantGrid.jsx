const UNITS = {
  'PM2.5': 'µg/m³', 'PM10': 'µg/m³', 'NO': 'µg/m³', 'NO2': 'µg/m³',
  'NOx': 'ppb', 'NH3': 'µg/m³', 'CO': 'mg/m³', 'SO2': 'µg/m³', 'O3': 'µg/m³',
}

export default function PollutantGrid({ pollutants, source }) {
  const entries = Object.entries(pollutants || {})
  return (
    <div>
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm text-muted tracking-wide">Live pollutant snapshot</h3>
        <span className={`text-[11px] px-2 py-0.5 rounded-full font-mono ${source === 'live' ? 'bg-tealx/15 text-tealx' : 'bg-haze/15 text-haze'}`}>
          {source === 'live' ? 'live CPCB feed' : 'simulated'}
        </span>
      </div>
      <div className="grid grid-cols-3 sm:grid-cols-3 gap-2">
        {entries.map(([name, value]) => (
          <div key={name} className="bg-panel border border-hairline rounded-lg px-3 py-2">
            <div className="text-xs text-muted">{name}</div>
            <div className="font-mono text-lg text-ink">
              {value}
              <span className="text-[10px] text-muted ml-1">{UNITS[name] || ''}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
