const BANDS = [
  { lo: 0, hi: 50, color: '#3DDC84' },
  { lo: 50, hi: 100, color: '#A8D93E' },
  { lo: 100, hi: 200, color: '#F2C230' },
  { lo: 200, hi: 300, color: '#F2914A' },
  { lo: 300, hi: 400, color: '#E0483C' },
  { lo: 400, hi: 500, color: '#8B1E2D' },
]

const START_ANGLE = -220
const END_ANGLE = 40
const SWEEP = END_ANGLE - START_ANGLE

function polar(cx, cy, r, angleDeg) {
  const rad = ((angleDeg - 90) * Math.PI) / 180
  return { x: cx + r * Math.cos(rad), y: cy + r * Math.sin(rad) }
}

function arcPath(cx, cy, r, a0, a1) {
  const p0 = polar(cx, cy, r, a0)
  const p1 = polar(cx, cy, r, a1)
  const large = a1 - a0 > 180 ? 1 : 0
  return `M ${p0.x} ${p0.y} A ${r} ${r} 0 ${large} 1 ${p1.x} ${p1.y}`
}

export default function AQIGauge({ value, label, color, city }) {
  const cx = 130, cy = 130, r = 96
  const clamped = Math.max(0, Math.min(500, value))
  const valueAngle = START_ANGLE + (clamped / 500) * SWEEP

  return (
    <div className="flex flex-col items-center">
      <svg width="260" height="200" viewBox="0 0 260 170" role="img" aria-label={`Current AQI ${Math.round(value)}, ${label}`}>
        {BANDS.map((b) => {
          const a0 = START_ANGLE + (b.lo / 500) * SWEEP
          const a1 = START_ANGLE + (b.hi / 500) * SWEEP
          return (
            <path
              key={b.lo}
              d={arcPath(cx, cy, r, a0, a1)}
              stroke={b.color}
              strokeWidth="14"
              strokeOpacity="0.85"
              fill="none"
              strokeLinecap="butt"
            />
          )
        })}
        {/* haze density ticks - decorative marks that thin out toward "Good" */}
        {Array.from({ length: 25 }).map((_, i) => {
          const a = START_ANGLE + (i / 24) * SWEEP
          const p0 = polar(cx, cy, r - 12, a)
          const p1 = polar(cx, cy, r - 12 - (i % 3 === 0 ? 6 : 3), a)
          return <line key={i} x1={p0.x} y1={p0.y} x2={p1.x} y2={p1.y} stroke="#3A4046" strokeWidth="1.5" />
        })}
        {/* needle */}
        <line
          x1={cx}
          y1={cy}
          x2={polar(cx, cy, r - 22, valueAngle).x}
          y2={polar(cx, cy, r - 22, valueAngle).y}
          stroke={color}
          strokeWidth="3"
          strokeLinecap="round"
        />
        <circle cx={cx} cy={cy} r="5" fill={color} />

        <text x={cx} y={cy + 34} textAnchor="middle" className="font-display" fontSize="34" fill="#ECEEF0" fontWeight="500">
          {Math.round(value)}
        </text>
        <text x={cx} y={cy + 54} textAnchor="middle" fontFamily="Inter, sans-serif" fontSize="12" fill="#8E979E" letterSpacing="0.04em">
          {city ? city.toUpperCase() : 'AQI'}
        </text>
      </svg>
      <div
        className="mt-1 px-3 py-1 rounded-full text-xs font-medium tracking-wide"
        style={{ backgroundColor: `${color}22`, color }}
      >
        {label}
      </div>
    </div>
  )
}
