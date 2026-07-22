import { useState } from 'react'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend,
} from 'recharts'
import { fetchScenario } from '../api'

function CustomTooltip({ active, payload, label }) {
  if (!active || !payload || !payload.length) return null
  return (
    <div className="bg-raised border border-hairline rounded-md px-3 py-2 text-xs">
      <div className="text-muted mb-1">{new Date(label).toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' })}</div>
      {payload.map((p) => (
        <div key={p.dataKey} className="font-mono text-sm" style={{ color: p.color }}>
          {p.name}: {Math.round(p.value)}
        </div>
      ))}
    </div>
  )
}

export default function ScenarioSimulator({ city }) {
  const [pct, setPct] = useState(30)
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  async function run() {
    setLoading(true)
    setError('')
    try {
      const r = await fetchScenario(city, pct)
      setResult(r)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  const chartData = result
    ? result.dates.map((d, i) => ({ date: d, baseline: result.baseline[i], scenario: result.scenario[i] }))
    : []

  return (
    <div className="bg-panel border border-hairline rounded-xl p-4">
      <h3 className="text-sm text-muted tracking-wide mb-1">Intervention simulator</h3>
      <p className="text-[11px] text-muted mb-4">
        Estimate the effect of source-reduction measures (traffic curbs, industrial curtailment, dust
        suppression — see recommended interventions below) before enacting them, modeled as a cut in
        ambient pollutant load.
      </p>

      <div className="flex items-center gap-4 mb-4 flex-wrap">
        <label className="text-sm text-ink flex items-center gap-3 flex-1 min-w-[220px]">
          <span className="text-muted whitespace-nowrap">Pollutant load cut</span>
          <input
            type="range"
            min="0"
            max="80"
            step="5"
            value={pct}
            onChange={(e) => setPct(Number(e.target.value))}
            className="flex-1 accent-haze"
          />
          <span className="font-mono text-haze w-12 text-right">{pct}%</span>
        </label>
        <button
          onClick={run}
          disabled={loading || !city}
          className="bg-haze text-[#241505] text-sm font-medium px-4 py-2 rounded-md hover:brightness-110 disabled:opacity-50 transition whitespace-nowrap"
        >
          {loading ? 'Simulating…' : 'Run scenario'}
        </button>
      </div>

      {error && <p className="text-sm text-band-verypoor mb-3">{error}</p>}

      {result && (
        <>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 mb-4">
            <div className="bg-raised border border-hairline rounded-lg px-3 py-2">
              <div className="text-[10px] text-muted">Baseline peak</div>
              <div className="font-mono text-lg text-ink">{Math.round(result.impact.peak_baseline)}</div>
            </div>
            <div className="bg-raised border border-hairline rounded-lg px-3 py-2">
              <div className="text-[10px] text-muted">Scenario peak</div>
              <div className="font-mono text-lg text-tealx">{Math.round(result.impact.peak_scenario)}</div>
            </div>
            <div className="bg-raised border border-hairline rounded-lg px-3 py-2">
              <div className="text-[10px] text-muted">Peak reduction</div>
              <div className="font-mono text-lg text-haze">
                −{Math.round(result.impact.peak_reduction)} <span className="text-xs">({result.impact.peak_reduction_pct}%)</span>
              </div>
            </div>
            <div className="bg-raised border border-hairline rounded-lg px-3 py-2">
              <div className="text-[10px] text-muted">Mean reduction</div>
              <div className="font-mono text-lg text-haze">−{Math.round(result.impact.mean_reduction)}</div>
            </div>
          </div>

          <ResponsiveContainer width="100%" height={220}>
            <LineChart data={chartData} margin={{ top: 5, right: 10, left: -10, bottom: 0 }}>
              <CartesianGrid stroke="#22262A" vertical={false} />
              <XAxis
                dataKey="date"
                tickFormatter={(d) => new Date(d).toLocaleDateString(undefined, { weekday: 'short' })}
                stroke="#8E979E"
                fontSize={11}
                tickLine={false}
                axisLine={{ stroke: '#282E32' }}
              />
              <YAxis stroke="#8E979E" fontSize={11} tickLine={false} axisLine={false} width={36} />
              <Tooltip content={<CustomTooltip />} />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              <Line type="monotone" dataKey="baseline" name="No intervention" stroke="#8E979E" strokeWidth={2} dot={false} />
              <Line type="monotone" dataKey="scenario" name={`${pct}% reduction`} stroke="#4FD1C5" strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </>
      )}
    </div>
  )
}
