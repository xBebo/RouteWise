import { hrefFor } from '../hooks/useHashRoute.js'
import { countsLabel } from '../lib/network.js'
import { Button } from './Button.jsx'
import { NodeGlyph } from './NodeGlyph.jsx'

const NAV_ITEMS = [
  {
    route: 'map',
    label: 'Network Map',
    icon: (
      <path
        d="M4 13l5-8 6 6M4 13h0M9 5h0M15 11h0"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    ),
    dots: [
      [4, 13],
      [9, 5],
      [15, 11],
    ],
  },
  {
    route: 'directory',
    label: 'Locations & Roads',
    icon: (
      <path
        d="M3 5h14M3 10h14M3 15h14"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinecap="round"
      />
    ),
    dots: [],
  },
]

function NavIcon({ item }) {
  return (
    <svg width="18" height="18" viewBox="0 0 20 20" aria-hidden="true" className="shrink-0">
      {item.icon}
      {item.dots.map(([cx, cy]) => (
        <circle key={`${cx}-${cy}`} cx={cx} cy={cy} r="2.1" fill="currentColor" />
      ))}
    </svg>
  )
}

/** Brand mark: a tiny network of a depot, a hub and a customer. */
function Brand() {
  return (
    <a href={hrefFor('map')} className="flex items-center gap-2.5 rounded-md">
      <svg width="28" height="28" viewBox="0 0 28 28" aria-hidden="true">
        <path d="M7 20L14 8l8 12z" fill="none" className="stroke-slate-300" strokeWidth="1.5" />
        <g transform="translate(7 20)">
          <NodeGlyph kind="DEPOT" radius={4} />
        </g>
        <g transform="translate(14 8)">
          <NodeGlyph kind="HUB" radius={4} />
        </g>
        <g transform="translate(22 20)">
          <NodeGlyph kind="CUSTOMER" radius={3.2} />
        </g>
      </svg>
      <span className="text-[15px] font-semibold tracking-tight text-slate-900">RouteWise</span>
    </a>
  )
}

function DataStatus({ status, counts }) {
  const states = {
    loading: { dot: 'bg-slate-400 motion-safe:animate-pulse', text: 'Loading network…' },
    error: { dot: 'bg-closed', text: 'API unavailable' },
    ready: {
      dot: 'bg-open',
      text: counts ? countsLabel(counts.locations, counts.roads) : 'Connected',
    },
  }
  const { dot, text } = states[status]
  return (
    <span className="flex min-w-0 items-center gap-2 text-xs text-slate-600">
      <span className={`size-2 shrink-0 rounded-full ${dot}`} aria-hidden="true" />
      <span className="truncate">{text}</span>
    </span>
  )
}

function ReloadIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 16 16" aria-hidden="true">
      <path
        d="M13.5 8a5.5 5.5 0 1 1-1.6-3.9M13.5 2.5v3h-3"
        fill="none"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}

/**
 * Persistent sidebar on desktop (lg+), compact top bar with a two-tab nav on
 * mobile. Both render the same NAV_ITEMS so the product feels identical.
 */
export function AppShell({ route, status, counts, onReload, children }) {
  return (
    <div className="min-h-dvh">
      <a
        href="#main"
        className="sr-only z-50 rounded-md bg-white px-3 py-2 text-sm font-medium shadow focus:not-sr-only focus:fixed focus:top-2 focus:left-2"
      >
        Skip to content
      </a>

      {/* Desktop sidebar */}
      <aside className="fixed inset-y-0 left-0 hidden w-60 flex-col border-r border-stone-200 bg-white lg:flex">
        <div className="px-5 pt-5 pb-6">
          <Brand />
          <p className="mt-1 pl-[38px] text-xs text-slate-500">Delivery network</p>
        </div>
        <nav aria-label="Primary" className="flex-1 px-3">
          <ul className="space-y-0.5">
            {NAV_ITEMS.map((item) => {
              const active = item.route === route
              return (
                <li key={item.route}>
                  <a
                    href={hrefFor(item.route)}
                    aria-current={active ? 'page' : undefined}
                    className={`flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors ${
                      active
                        ? 'bg-accent-50 text-accent-700 shadow-[inset_2px_0_0_var(--color-accent-600)]'
                        : 'text-slate-700 hover:bg-stone-100 hover:text-slate-900'
                    }`}
                  >
                    <NavIcon item={item} />
                    {item.label}
                  </a>
                </li>
              )
            })}
          </ul>
        </nav>
        <div className="space-y-2 border-t border-stone-200 px-5 py-4">
          <p className="text-[11px] font-medium tracking-wide text-slate-500 uppercase">Flask API</p>
          <div className="flex items-center justify-between gap-2">
            <DataStatus status={status} counts={counts} />
            <Button
              variant="ghost"
              size="sm"
              onClick={onReload}
              disabled={status === 'loading'}
              aria-label="Reload network data"
              title="Reload network data"
              className="w-8 px-0"
            >
              <ReloadIcon />
            </Button>
          </div>
        </div>
      </aside>

      {/* Mobile top bar */}
      <header className="sticky top-0 z-30 border-b border-stone-200 bg-white lg:hidden">
        <div className="flex items-center justify-between gap-3 px-4 pt-3 pb-2">
          <Brand />
          <div className="flex min-w-0 items-center gap-1">
            <DataStatus status={status} counts={counts} />
            <Button
              variant="ghost"
              size="sm"
              onClick={onReload}
              disabled={status === 'loading'}
              aria-label="Reload network data"
              className="w-9 px-0"
            >
              <ReloadIcon />
            </Button>
          </div>
        </div>
        <nav aria-label="Primary" className="px-4 pb-2.5">
          <ul className="grid grid-cols-2 gap-1 rounded-lg bg-stone-100 p-1">
            {NAV_ITEMS.map((item) => {
              const active = item.route === route
              return (
                <li key={item.route}>
                  <a
                    href={hrefFor(item.route)}
                    aria-current={active ? 'page' : undefined}
                    className={`flex h-9 items-center justify-center gap-2 rounded-md text-sm font-medium ${
                      active ? 'bg-white text-accent-700 shadow-sm ring-1 ring-stone-200' : 'text-slate-600'
                    }`}
                  >
                    <NavIcon item={item} />
                    {item.label}
                  </a>
                </li>
              )
            })}
          </ul>
        </nav>
      </header>

      <main id="main" tabIndex={-1} className="flex min-h-[calc(100dvh-105px)] flex-col focus:outline-none lg:ml-60 lg:h-dvh lg:min-h-0 lg:overflow-y-auto">
        {children}
      </main>
    </div>
  )
}
