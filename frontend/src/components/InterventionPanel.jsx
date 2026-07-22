const STAGE_COLOR = { I: '#F2C230', II: '#F2914A', III: '#E0483C', IV: '#8B1E2D' }

function SourceBar({ label, sharePct }) {
  return (
    <div className="mb-2.5">
      <div className="flex justify-between text-xs text-muted mb-1">
        <span>{label}</span>
        <span className="font-mono">{sharePct}%</span>
      </div>
      <div className="h-1.5 rounded-full bg-raised overflow-hidden">
        <div className="h-full bg-haze rounded-full" style={{ width: `${sharePct}%` }} />
      </div>
    </div>
  )
}

export default function InterventionPanel({ data, loading }) {
  if (loading) {
    return <div className="bg-panel border border-hairline rounded-xl p-4 text-sm text-muted">Loading intervention analysis…</div>
  }
  if (!data) return null

  const { source_attribution, intervention_plan, current_aqi_estimate } = data

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
      <div className="bg-panel border border-hairline rounded-xl p-4">
        <h3 className="text-sm text-muted tracking-wide mb-1">Suspected pollution sources</h3>
        <p className="text-[11px] text-muted mb-4">
          Indicative signature-based ranking from current pollutant mix — a prioritization hint, not certified source apportionment.
        </p>
        {source_attribution.map((s) => (
          <SourceBar key={s.source} label={s.label} sharePct={s.share_pct} />
        ))}
      </div>

      <div className="bg-panel border border-hairline rounded-xl p-4">
        <div className="flex items-center justify-between mb-1">
          <h3 className="text-sm text-muted tracking-wide">Recommended interventions</h3>
          {intervention_plan.stage && (
            <span
              className="text-[11px] px-2 py-0.5 rounded-full font-mono"
              style={{ backgroundColor: `${STAGE_COLOR[intervention_plan.stage]}22`, color: STAGE_COLOR[intervention_plan.stage] }}
            >
              GRAP Stage {intervention_plan.stage}
            </span>
          )}
        </div>
        <p className="text-[11px] text-muted mb-3">{intervention_plan.note}</p>

        {intervention_plan.actions.length === 0 ? (
          <p className="text-sm text-muted italic">No stage-level action triggered at current AQI (~{Math.round(current_aqi_estimate)}).</p>
        ) : (
          <ul className="space-y-2 max-h-72 overflow-y-auto pr-1">
            {intervention_plan.actions.map((a, i) => (
              <li
                key={i}
                className={`text-sm border rounded-lg px-3 py-2 ${a.priority ? 'border-haze/40 bg-haze/5' : 'border-hairline'}`}
              >
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-raised text-muted">Stage {a.stage}</span>
                  <span className="text-[10px] text-tealx">{a.source_label}</span>
                  {a.priority && <span className="text-[10px] text-haze ml-auto">priority</span>}
                </div>
                <div className="text-ink">{a.action}</div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}
