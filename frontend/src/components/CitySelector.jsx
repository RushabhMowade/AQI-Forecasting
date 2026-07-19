export default function CitySelector({ cities, value, onChange, onSubmit, loading }) {
  return (
    <div className="flex items-center gap-3">
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="bg-raised border border-hairline text-ink text-sm rounded-md px-3 py-2 focus:outline-none focus:border-haze"
      >
        {cities.map((c) => (
          <option key={c} value={c}>{c}</option>
        ))}
      </select>
      <button
        onClick={onSubmit}
        disabled={loading}
        className="bg-haze text-[#241505] text-sm font-medium px-4 py-2 rounded-md hover:brightness-110 disabled:opacity-50 transition"
      >
        {loading ? 'Forecasting…' : 'Generate forecast'}
      </button>
    </div>
  )
}
