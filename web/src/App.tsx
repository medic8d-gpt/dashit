import React from 'react'
import Header from './components/Header'
import { fetchLatestBySources, type Article } from './lib/api'
import Carousel from './components/Carousel'

const SOURCES = ['lex18', 'wkyt', 'wtvq', 'fox56'] as const

export default function App() {
  const [items, setItems] = React.useState<Article[]>([])
  const [loading, setLoading] = React.useState(true)
  const [error, setError] = React.useState('')

  React.useEffect(() => {
    let cancelled = false
    setLoading(true)
    fetchLatestBySources(SOURCES as any, 10)
      .then((list) => { if (!cancelled) setItems(list) })
      .catch((e) => { if (!cancelled) setError(String(e?.message || e)) })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [])

  return (
    <div className="app">
      <Header title="LexingtonKY News" subtitle="Latest from LEX18, WKYT, WTVQ, FOX56" />
      {loading && <p className="status">Loading latest articles…</p>}
      {error && <p className="error">{error}</p>}
      {!loading && !error && <Carousel items={items} />}
    </div>
  )
}
