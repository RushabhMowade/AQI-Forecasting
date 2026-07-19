import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceArea,
} from 'recharts'

const BANDS = [
  { y0: 0, y1: 50, color: '#3DDC84' },
  { y0: 50, y1: 100, color: '#A8D93E' },
  { y0: 100, y1: 200, color: '#F2C230' },
  { y0: 200, y1: 300, color: '#F2914A' },
  { y0: 300, y1: 400, color: '#E0483C' },
  { y0: 400, y1: 500, color: '#8B1E2D' },
]

function CustomTooltip({ active, payload, label }) {
  if (!active || !payload || !payload.length) return null
  return (
    <div className="bg-raised border border-hairline rounded-md px-3 py-2 text-xs">
      <div className="text-muted mb-1">{new Date(label).toLocaleString(undefined, { weekday: 'short', hour: 'numeric' })}</div>
      <div className="text-ink font-mono text-sm">AQI {Math.round(payload[0].value)}</div>
    </div>
  )
}

export default function ForecastChart({ timestamps, predictions }) {
  const data = timestamps.map((t, i) => ({ time: t, aqi: predictions[i] }))
  const maxY = Math.max(150, ...predictions) * 1.1

  return (
    <div className="bg-panel border border-hairline rounded-xl p-4">
      <h3 className="text-sm text-muted tracking-wide mb-3">72-hour AQI forecast</h3>
      <ResponsiveContainer width="100%" height={280}>
        <AreaChart data={data} margin={{ top: 5, right: 10, left: -10, bottom: 0 }}>
          <defs>
            <linearGradient id="aqiFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#E8A853" stopOpacity={0.35} />
              <stop offset="100%" stopColor="#E8A853" stopOpacity={0.02} />
            </linearGradient>
          </defs>
          {BANDS.map((b) => (
            <ReferenceArea key={b.y0} y1={b.y0} y2={Math.min(b.y1, maxY)} fill={b.color} fillOpacity={0.06} strokeWidth={0} />
          ))}
          <CartesianGrid stroke="#22262A" vertical={false} />
          <XAxis
            dataKey="time"
            tickFormatter={(t) => new Date(t).toLocaleDateString(undefined, { weekday: 'short' })}
            interval={11}
            stroke="#8E979E"
            fontSize={11}
            tickLine={false}
            axisLine={{ stroke: '#282E32' }}
          />
          <YAxis domain={[0, maxY]} stroke="#8E979E" fontSize={11} tickLine={false} axisLine={false} width={36} />
          <Tooltip content={<CustomTooltip />} />
          <Area type="monotone" dataKey="aqi" stroke="#E8A853" strokeWidth={2} fill="url(#aqiFill)" dot={false} />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  )
}
