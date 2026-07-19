export default function Banner({ peak }) {
  if (!peak) return null
  let icon = '🍃'
  if (peak.value > 300) icon = '🚨'
  else if (peak.value > 100) icon = '😷'

  return (
    <div
      className="rounded-lg border px-4 py-3 text-sm flex items-start gap-3"
      style={{ borderColor: `${peak.color}55`, backgroundColor: `${peak.color}14`, color: peak.color }}
    >
      <span className="text-base leading-none">{icon}</span>
      <span className="text-ink">
        Peak forecast: <span className="font-mono" style={{ color: peak.color }}>{Math.round(peak.value)}</span> ({peak.label}) around hour {peak.hour} of the 72-hour window.
      </span>
    </div>
  )
}
