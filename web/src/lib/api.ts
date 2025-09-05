export interface Article {
  id: number
  hash?: string | null
  source: string
  url: string
  headline: string
  summary?: string | null
  published?: string | null
  posted: number
}

const BASE = '/api'

async function fetchJSON<T>(path: string): Promise<T> {
  const r = await fetch(BASE + path)
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`)
  return r.json() as Promise<T>
}

export async function fetchLatestBySources(sources: readonly string[], perSource: number): Promise<Article[]> {
  // Use the general /articles endpoint with id_desc to avoid bad date ordering
  const lists = await Promise.all(
    sources.map((s) => fetchJSON<Article[]>(`/articles?source=${encodeURIComponent(s)}&limit=${perSource}&sort=id_desc`))
  )
  const merged = lists.flat()

  // De-dupe by hash or url
  const seen = new Set<string>()
  const dedup: Article[] = []
  for (const a of merged) {
    const key = a.hash || a.url
    if (!seen.has(key)) { seen.add(key); dedup.push(a) }
  }

  // Optional freshness filter: drop items older than 365 days when a valid date is present
  const now = Date.now()
  const ONE_YEAR = 365 * 24 * 3600 * 1000
  const fresh = dedup.filter((a) => {
    if (!a.published) return true
    const t = Date.parse(a.published)
    if (Number.isNaN(t)) return true
    return now - t <= ONE_YEAR
  })

  // Final ordering by ID (newest first)
  fresh.sort((a, b) => b.id - a.id)
  return fresh
}
