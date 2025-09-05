import React from 'react'
import type { Article } from '../lib/api'

interface Props {
  items: Article[]
}

export default function Carousel({ items }: Props) {
  const containerRef = React.useRef<HTMLDivElement>(null)
  const trackRef = React.useRef<HTMLDivElement>(null)
  const [widths, setWidths] = React.useState<number[]>([])
  const [offset, setOffset] = React.useState(0)

  const speed = 18 // px per second, right->left (slower)

  // Measure item widths for seamless loop
  React.useLayoutEffect(() => {
    const el = trackRef.current
    if (!el) return
    const w: number[] = []
    el.querySelectorAll('.card').forEach((n) => w.push((n as HTMLElement).offsetWidth))
    setWidths(w)
  }, [items])

  // Auto scroll loop
  React.useEffect(() => {
    let raf = 0
    let last = performance.now()
    function tick(t: number) {
      const dt = (t - last) / 1000
      last = t
      setOffset((prev) => prev + speed * dt)
      raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [])

  // Reset offset when it exceeds first cycle
  const totalWidth = React.useMemo(() => widths.reduce((a, b) => a + b, 0), [widths])
  const effective = totalWidth > 0 ? (offset % totalWidth) : 0

  // Duplicate items for looping
  const loopItems = React.useMemo(() => items.concat(items), [items])

  // Effect values for center highlight
  const computeStyle = (card: HTMLDivElement | null): React.CSSProperties => {
    const container = containerRef.current
    if (!card || !container) return {}
    const rect = card.getBoundingClientRect()
    const cRect = container.getBoundingClientRect()
    const cardCenter = rect.left + rect.width / 2
    const containerCenter = cRect.left + cRect.width / 2
    const dx = Math.abs(cardCenter - containerCenter)
    const max = cRect.width / 2
    const pct = Math.min(1, dx / max) // 0 center → 1 edges
    const blur = 6 * pct
    const brightness = 1.1 - 0.5 * pct
    const scale = 1.0 + 0.06 * (1 - pct)
    const opacity = 1 - 0.35 * pct
    return {
      filter: `blur(${blur.toFixed(2)}px) brightness(${brightness.toFixed(2)})`,
      transform: `scale(${scale.toFixed(3)})`,
      opacity,
    }
  }

  return (
    <div ref={containerRef} className="carousel">
      <div
        ref={trackRef}
        className="track"
        style={{ transform: `translateX(${-effective}px)` }}
      >
        {loopItems.map((a, i) => (
          <Card key={a.id + ':' + i} article={a} computeStyle={computeStyle} />
        ))}
      </div>
    </div>
  )
}

function Card({ article, computeStyle }: { article: Article; computeStyle: (el: HTMLDivElement | null) => React.CSSProperties }) {
  const ref = React.useRef<HTMLDivElement>(null)
  const [style, setStyle] = React.useState<React.CSSProperties>({})

  React.useEffect(() => {
    let raf = 0
    const update = () => {
      setStyle(computeStyle(ref.current))
      raf = requestAnimationFrame(update)
    }
    raf = requestAnimationFrame(update)
    return () => cancelAnimationFrame(raf)
  }, [computeStyle])

  const dt = timeAgo(article.published)

  return (
    <div ref={ref} className="card" style={style}>
      <a href={article.url} target="_blank" rel="noreferrer">
        <div className="meta">
          <span className="source">{article.source.toUpperCase()}</span>
          <span className="dot">•</span>
          <span className="time">{dt}</span>
        </div>
        <div className="headline">{article.headline}</div>
      </a>
    </div>
  )
}

function timeAgo(iso?: string | null) {
  if (!iso) return ''
  const t = new Date(iso).getTime()
  if (!t) return ''
  const s = Math.floor((Date.now() - t) / 1000)
  if (s < 60) return `${s}s ago`
  const m = Math.floor(s / 60)
  if (m < 60) return `${m}m ago`
  const h = Math.floor(m / 60)
  if (h < 24) return `${h}h ago`
  const d = Math.floor(h / 24)
  return `${d}d ago`
}
