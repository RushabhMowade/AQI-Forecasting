const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

export async function fetchCities() {
  const res = await fetch(`${API_BASE}/api/cities`, { cache: 'no-store' })
  if (!res.ok) throw new Error('Could not load city list')
  const data = await res.json()
  return data.cities
}

export async function fetchForecast(city) {
  const res = await fetch(`${API_BASE}/api/forecast?city=${encodeURIComponent(city)}`, { cache: 'no-store' })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.detail || 'Forecast request failed')
  }
  return res.json()
}

export async function fetchInterventions(city) {
  const res = await fetch(`${API_BASE}/api/interventions?city=${encodeURIComponent(city)}`, { cache: 'no-store' })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.detail || 'Interventions request failed')
  }
  return res.json()
}

export async function fetchScenario(city, pollutantReductionPct) {
  const params = new URLSearchParams({ city, pollutant_reduction_pct: String(pollutantReductionPct) })
  const res = await fetch(`${API_BASE}/api/scenario?${params.toString()}`, { cache: 'no-store' })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.detail || 'Scenario request failed')
  }
  return res.json()
}
