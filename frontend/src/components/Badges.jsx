import { kindMeta } from '../lib/network.js'
import { KindIcon } from './NodeGlyph.jsx'

const base = 'inline-flex items-center gap-1.5 whitespace-nowrap rounded px-1.5 py-0.5 text-xs font-medium'

export function KindBadge({ kind }) {
  return (
    <span className={`${base} bg-stone-100 text-slate-700`}>
      <KindIcon kind={kind} size={12} />
      {kindMeta(kind).label}
    </span>
  )
}

/** Open / Closed: icon + word, never colour alone. */
export function RoadStatusBadge({ closed }) {
  return closed ? (
    <span className={`${base} bg-closed-50 text-closed ring-1 ring-inset ring-closed/30`}>
      <svg width="10" height="10" viewBox="0 0 10 10" aria-hidden="true">
        <path d="M2 2l6 6M8 2l-6 6" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" />
      </svg>
      Closed
    </span>
  ) : (
    <span className={`${base} text-open`}>
      <svg width="10" height="10" viewBox="0 0 10 10" aria-hidden="true">
        <path
          d="M1.5 5.5l2.3 2.2L8.5 2.5"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.8"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
      Open
    </span>
  )
}

/** One-way / Two-way with an arrow glyph. `relation` lets the inspector say Inbound/Outbound. */
export function DirectionLabel({ oneWay, relation }) {
  const text = relation ?? (oneWay ? 'One-way' : 'Two-way')
  return (
    <span
      className={`inline-flex items-center gap-1.5 whitespace-nowrap text-xs ${
        oneWay ? 'font-medium text-accent-700' : 'text-slate-600'
      }`}
    >
      <svg width="16" height="10" viewBox="0 0 16 10" aria-hidden="true">
        <path
          d={oneWay ? 'M1 5h12M9.5 1.5L13.5 5l-4 3.5' : 'M3 5h10M5.5 1.5L2 5l3.5 3.5M10.5 1.5L14 5l-3.5 3.5'}
          fill="none"
          stroke="currentColor"
          strokeWidth="1.6"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
      {text}
    </span>
  )
}

export function IsolatedBadge() {
  return <span className={`${base} border border-dashed border-slate-400 text-slate-600`}>Isolated</span>
}
