import { kindMeta } from '../lib/network.js'

/**
 * The shape for a location kind, centred on (0, 0) so it can be placed with a
 * <g transform>. Depot = square, Hub = diamond, Customer = circle: shape carries
 * the meaning, colour reinforces it.
 */
export function NodeGlyph({ kind, radius = kindMeta(kind).radius }) {
  if (kind === 'DEPOT') {
    return (
      <rect
        x={-radius}
        y={-radius}
        width={radius * 2}
        height={radius * 2}
        rx={2}
        className="fill-slate-900 stroke-white"
        strokeWidth={1.5}
      />
    )
  }
  if (kind === 'HUB') {
    const r = radius * 1.2
    return (
      <polygon
        points={`0,${-r} ${r},0 0,${r} ${-r},0`}
        className="fill-accent-600 stroke-white"
        strokeWidth={1.5}
        strokeLinejoin="round"
      />
    )
  }
  return <circle r={radius} className="fill-white stroke-slate-600" strokeWidth={2} />
}

/** The same glyph as a small inline icon for HTML contexts (tables, legend). */
export function KindIcon({ kind, size = 14 }) {
  const radius = kind === 'CUSTOMER' ? 4.5 : 5
  return (
    <svg width={size} height={size} viewBox="-7 -7 14 14" aria-hidden="true" className="shrink-0">
      <NodeGlyph kind={kind} radius={radius} />
    </svg>
  )
}
