import React from 'react'

// Use a relative path by default so NGINX or the Vite dev proxy
// can avoid CORS preflights (it maps /api -> 127.0.0.1:4000)
const DEFAULT_OPENAPI_URL = (import.meta as any).env?.VITE_OPENAPI_URL ||
  '/api/openapi.json'

export function useOpenAPISpec() {
  const [url, setUrl] = React.useState<string>(DEFAULT_OPENAPI_URL)
  const [spec, setSpec] = React.useState<any>(null)
  const [loading, setLoading] = React.useState<boolean>(true)
  const [error, setError] = React.useState<string>('')
  const [servers, setServers] = React.useState<string[]>([])
  const [selectedServer, setSelectedServer] = React.useState<string>('http://127.0.0.1:4000')

  React.useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError('')
    fetch(url)
      .then((r) => r.json())
      .then((json) => {
        if (cancelled) return
        if (!json.openapi?.startsWith('3.1')) {
          throw new Error(`Spec must be OpenAPI 3.1.x, got ${json.openapi}`)
        }
        setSpec(json)
        const list: string[] = (json.servers || []).map((s: any) => s.url)
        if (!list.length) list.push('http://127.0.0.1:4000')
        setServers(list)
        setSelectedServer(list[0])
      })
      .catch((e) => setError(String(e.message || e)))
      .finally(() => setLoading(false))
    return () => { cancelled = true }
  }, [url])

  return { spec, url, setUrl, servers, selectedServer, setSelectedServer, loading, error }
}
