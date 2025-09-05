import React from 'react'

export default function Header({ title, subtitle }: { title: string; subtitle?: string }) {
  return (
    <header className="header">
      <img src="/vite.svg" alt="Logo" width={28} height={28} />
      <div>
        <h1 style={{ margin: 0, fontSize: 18 }}>{title}</h1>
        {subtitle && <div className="muted" style={{ fontSize: 12 }}>{subtitle}</div>}
      </div>
    </header>
  )
}
