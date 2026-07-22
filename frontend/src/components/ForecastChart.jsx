import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceArea, Cell,
} from 'recharts'

const BANDS = [
  { y0: 0, y1: 50, color: '#3DDC84' },
  { y0: 50, y1: 100, color: '#A8D93E' },
  { y0: 100, y1: 200, color: '#F2C230' },
  { y0: 200, y1: 300, color: '#F2914A' },
  { y0: 300, y1: 400, color: '#E0483C' },
  { y0: 400, y1: 500, color: '#8B1E2D' },
]

function bandColor(value) {
  const band = BANDS.find((b) => value >= b.y0 && value <= b.y1)
  return band ? band.color : '#8B1E2D'
}

function CustomTooltip({ active, payload, label }) {
  if (!active || !payload || !payload.length) return null
  return (
    <div className="bg-raised border border-hairline rounded-md px-3 py-2 text-xs">
      <div className="text-muted mb-1">{new Date(label).toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' })}</div>
      <div className="text-ink font-mono text-sm">AQI {Math.round(payload[0].value)}</div>
    </div>
  )
}

export default function ForecastChart({ dates, outlook }) {
  const data = dates.map((d, i) => ({ date: d, aqi: outlook[i] }))
  const maxY = Math.max(150, ...outlook) * 1.15

  return (
    <div className="bg-panel border border-hairline rounded-xl p-4">
      <h3 className="text-sm text-muted tracking-wide mb-1">Outlook</h3>
      <p className="text-[11px] text-muted mb-3">
        Not a learned time-series prediction — the same accurate model re-run daily against the live reading,
        adjusted only by real forecast wind speed (dispersion heuristic). See "About this forecast" below.
      </p>
      <ResponsiveContainer width="100%" height={240}>
        <BarChart data={data} margin={{ top: 5, right: 10, left: -10, bottom: 0 }}>
          {BANDS.map((b) => (
            <ReferenceArea key={b.y0} y1={b.y0} y2={Math.min(b.y1, maxY)} fill={b.color} fillOpacity={0.06} strokeWidth={0} />
          ))}
          <CartesianGrid stroke="#22262A" vertical={false} />
          <XAxis
            dataKey="date"
            tickFormatter={(d) => new Date(d).toLocaleDateString(undefined, { weekday: 'short' })}
            stroke="#8E979E"
            fontSize={11}
            tickLine={false}
            axisLine={{ stroke: '#282E32' }}
          />
          <YAxis domain={[0, maxY]} stroke="#8E979E" fontSize={11} tickLine={false} axisLine={false} width={36} />
          <Tooltip content={<CustomTooltip />} cursor={{ fill: '#ffffff08' }} />
          <Bar dataKey="aqi" radius={[6, 6, 0, 0]} maxBarSize={64}>
            {data.map((d, i) => (
              <Cell key={i} fill={bandColor(d.aqi)} fillOpacity={0.85} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
