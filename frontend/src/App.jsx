import { useEffect, useState } from 'react'
import { fetchCities, fetchForecast } from './api'
import CitySelector from './components/CitySelector'
import AQIGauge from './components/AQIGauge'
import PollutantGrid from './components/PollutantGrid'
import ForecastChart from './components/ForecastChart'
import Banner from './components/Banner'
import InfoPanel from './components/InfoPanel'

export default function App() {
  const [cities, setCities] = useState([])
  const [city, setCity] = useState('')
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)
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
    setError('')
    try {
      const result = await fetchForecast(city)
      setData(result)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-base text-ink font-sans">
      <div className="max-w-4xl mx-auto px-5 py-8">
        <header className="flex items-center justify-between flex-wrap gap-4 mb-8">
          <div>
            <h1 className="font-display text-2xl">Hyperlocal AQI Forecast</h1>
            <p className="text-sm text-muted mt-1">72-hour air quality projection from live CPCB readings and weather</p>
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
              <div className="bg-panel border border-hairline rounded-xl p-4 flex items-center justify-center">
                <AQIGauge value={data.current.value} label={data.current.label} color={data.current.color} city={data.city} />
              </div>
              <div className="bg-panel border border-hairline rounded-xl p-4">
                <PollutantGrid pollutants={data.pollutants} source={data.data_sources?.pollutants} />
              </div>
            </div>

            <ForecastChart timestamps={data.timestamps} predictions={data.predictions} />

            <InfoPanel sources={data.data_sources} />
          </div>
        )}
      </div>
    </div>
  )
}
