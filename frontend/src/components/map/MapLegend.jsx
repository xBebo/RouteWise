import { useId } from 'react'
import { KindIcon } from '../NodeGlyph.jsx'

function LineSample({ variant }) {
  return (
    <svg width="28" height="12" viewBox="0 0 28 12" aria-hidden="true" className="shrink-0">
      {variant === 'two-way' && <line x1="2" y1="6" x2="26" y2="6" className="stroke-slate-400" strokeWidth="1.75" />}
      {variant === 'one-way' && (
        <>
          <line x1="2" y1="6" x2="20" y2="6" className="stroke-slate-500" strokeWidth="1.75" />
          <path d="M18 1.5L27 6L18 10.5z" className="fill-accent-600" />
        </>
      )}
      {variant === 'closed' && (
        <>
          <line x1="2" y1="6" x2="26" y2="6" className="stroke-closed" strokeWidth="1.75" strokeDasharray="4 3" />
          <circle cx="14" cy="6" r="5" className="fill-white stroke-closed" strokeWidth="1.25" />
          <path d="M12 4l4 4M16 4l-4 4" className="stroke-closed" strokeWidth="1.4" strokeLinecap="round" />
        </>
      )}
    </svg>
  )
}

const items = [
  { key: 'depot', icon: <KindIcon kind="DEPOT" />, label: 'Depot' },
  { key: 'hub', icon: <KindIcon kind="HUB" />, label: 'Hub' },
  { key: 'customer', icon: <KindIcon kind="CUSTOMER" />, label: 'Customer' },
  {
    key: 'isolated',
    icon: (
      <svg width="14" height="14" viewBox="-7 -7 14 14" aria-hidden="true">
        <circle r="6" fill="none" className="stroke-slate-500" strokeDasharray="2.5 2" />
        <circle r="3" className="fill-white stroke-slate-600" strokeWidth="1.5" />
      </svg>
    ),
    label: 'No roads',
  },
  { key: 'two-way', icon: <LineSample variant="two-way" />, label: 'Two-way' },
  { key: 'one-way', icon: <LineSample variant="one-way" />, label: 'One-way' },
  { key: 'closed', icon: <LineSample variant="closed" />, label: 'Closed' },
]

export function MapLegend({ className = '' }) {
  const titleId = useId() // rendered twice (mobile + desktop), so ids must be unique
  return (
    <section aria-labelledby={titleId} className={className}>
      <h2 id={titleId} className="mb-2 text-[11px] font-medium tracking-wide text-slate-500 uppercase">
        Legend
      </h2>
      <ul className="grid grid-cols-2 gap-x-5 gap-y-1.5 text-xs text-slate-700 sm:flex sm:flex-wrap lg:grid">
        {items.map((item) => (
          <li key={item.key} className="flex items-center gap-2">
            <span className="flex w-7 justify-center">{item.icon}</span>
            {item.label}
          </li>
        ))}
      </ul>
      <p className="mt-2 text-[11px] leading-snug text-slate-500">
        Schematic: positions come from location x/y, not geography. Distances in km; labels that would overlap
        are hidden until you select the road.
      </p>
    </section>
  )
}
