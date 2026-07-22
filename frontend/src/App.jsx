import { useEffect, useState } from 'react'
import { fetchCities, fetchForecast, fetchInterventions } from './api'
import CitySelector from './components/CitySelector'
import AQIGauge from './components/AQIGauge'
import PollutantGrid from './components/PollutantGrid'
import ForecastChart from './components/ForecastChart'
import Banner from './components/Banner'
import InfoPanel from './components/InfoPanel'
import InterventionPanel from './components/InterventionPanel'
import ScenarioSimulator from './components/ScenarioSimulator'

export default function App() {
  const [cities, setCities] = useState([])
  const [city, setCity] = useState('')
  const [data, setData] = useState(null)
  const [interventions, setInterventions] = useState(null)
  const [loading, setLoading] = useState(false)
  const [interventionsLoading, setInterventionsLoading] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    fetchCities()
      .then((list) => {
        setCities(list)
        if (list.length) setCity(list[0])
      })
      .catch(() => setError('Could not reach the forecast API. Is the backend running on port 8000?'))
  }, [])

  async function runForecast() {
    if (!city) return
    setLoading(true)
    setInterventionsLoading(true)
    setError('')
    try {
      const [result, plan] = await Promise.all([
        fetchForecast(city),
        fetchInterventions(city).catch(() => null),
      ])
      setData(result)
      setInterventions(plan)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
      setInterventionsLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-base text-ink font-sans">
      <div className="max-w-5xl mx-auto px-5 py-8">
        <header className="flex items-center justify-between flex-wrap gap-4 mb-8">
          <div>
            <h1 className="font-display text-2xl">AQI Intelligence & Intervention Console</h1>
            <p className="text-sm text-muted mt-1">Live CPCB-driven AQI, source attribution, and a quantified intervention simulator</p>
          </div>
          {cities.length > 0 && (
            <CitySelector cities={cities} value={city} onChange={setCity} onSubmit={runForecast} loading={loading} />
          )}
        </header>

        {error && (
          <div className="border border-band-verypoor/40 bg-band-verypoor/10 text-band-verypoor rounded-lg px-4 py-3 text-sm mb-6">
            {error}
          </div>
        )}

        {!data && !error && (
          <div className="border border-hairline rounded-xl px-6 py-16 text-center text-muted">
            Select a city and generate a forecast to see it here.
          </div>
        )}

        {data && (
          <div className="space-y-6">
            <Banner peak={data.peak} />

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div className="bg-panel border border-hairline rounded-xl p-4 flex flex-col items-center justify-center">
                <AQIGauge value={data.current.value} label={data.current.label} color={data.current.color} city={data.city} />
                <p className="text-[11px] text-muted mt-3 text-center">
                  Computed by the retrained model from live pollutant readings (MAE 0.78, R² 99.96% on held-out data).
                </p>
                {data.reference_aqi != null && (
                  <div className="mt-2 px-3 py-1.5 rounded-lg bg-raised border border-hairline text-xs text-center">
                    <span className="text-muted">Official reading (WAQI/CPCB): </span>
                    <span className="font-mono text-ink">{Math.round(data.reference_aqi)}</span>
                  </div>
                )}
              </div>
              <div className="bg-panel border border-hairline rounded-xl p-4">
                <PollutantGrid pollutants={data.pollutants} source={data.data_sources?.pollutants} />
              </div>
            </div>

            <ForecastChart dates={data.dates} outlook={data.outlook} />

            <InterventionPanel data={interventions} loading={interventionsLoading} />

            <ScenarioSimulator city={city} />

            <InfoPanel sources={data.data_sources} />
          </div>
        )}
      </div>
    </div>
  )
}
