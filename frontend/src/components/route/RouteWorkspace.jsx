import { NetworkMap } from '../map/NetworkMap.jsx'

function Badge({ className, children }) {
  return (
    <svg width="16" height="16" viewBox="-8 -8 16 16" aria-hidden="true" className="shrink-0">
      <circle r="7.5" className={className} />
      <text textAnchor="middle" dominantBaseline="central" className="fill-white text-[9px] font-semibold">
        {children}
      </text>
    </svg>
  )
}

/** Key for the route overlay, drawn on the map's corner. */
function RouteLegend({ mode }) {
  return (
    <ul className="pointer-events-none absolute bottom-2 left-2 flex flex-wrap items-center gap-x-3 gap-y-1 rounded-md border border-stone-200 bg-white/95 px-2.5 py-1.5 text-[11px] text-slate-700 shadow-sm">
      <li className="flex items-center gap-1.5">
        <svg width="22" height="10" viewBox="0 0 22 10" aria-hidden="true">
          <line x1="2" y1="5" x2="20" y2="5" className="stroke-accent-600" strokeWidth="5" strokeLinecap="round" />
        </svg>
        Planned route
      </li>
      <li className="flex items-center gap-1.5">
        <Badge className="fill-slate-900">S</Badge>Start
      </li>
      {mode === 'RUN' ? (
        <li className="flex items-center gap-1.5">
          <Badge className="fill-accent-600">1</Badge>Stop order
        </li>
      ) : (
        <li className="flex items-center gap-1.5">
          <Badge className="fill-accent-700">E</Badge>End
        </li>
      )}
    </ul>
  )
}

/**
 * Shared layout for Route Planner and Route History.
 * Desktop: one scrolling column (controls, then result) beside a full-height map.
 * Mobile: controls, map, result, stacked in that order (the column uses
 * `display: contents` so its two blocks can sit either side of the map).
 */
export function RouteWorkspace({ index, route, controls, result }) {
  return (
    <div className="flex flex-1 flex-col lg:min-h-0 lg:flex-row">
      {/* lg:relative contains the sr-only (absolute) text so it can't stretch the document. */}
      <div className="contents lg:relative lg:flex lg:w-[26rem] lg:shrink-0 lg:flex-col lg:overflow-y-auto lg:border-r lg:border-stone-200 lg:bg-white">
        <div className="order-1 border-b border-stone-200 bg-white">{controls}</div>
        {result && <div className="order-3 bg-white">{result}</div>}
      </div>
      <section aria-label="Route map" className="relative order-2 flex flex-col border-b border-stone-200 bg-stone-50 lg:min-w-0 lg:flex-1 lg:border-b-0">
        <div className="relative aspect-[4/5] max-h-[65dvh] w-full sm:aspect-[4/3] lg:aspect-auto lg:max-h-none lg:flex-1">
          <NetworkMap index={index} route={route} />
          {route && <RouteLegend mode={route.mode} />}
        </div>
      </section>
    </div>
  )
}
