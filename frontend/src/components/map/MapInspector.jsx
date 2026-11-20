import {
  coincidentCount,
  describeRoad,
  formatCoord,
  formatKm,
  kindMeta,
  locationCode,
  locationName,
  networkSummary,
} from '../../lib/network.js'
import { DirectionLabel, IsolatedBadge, KindBadge, RoadStatusBadge } from '../Badges.jsx'
import { Button } from '../Button.jsx'
import { KindIcon } from '../NodeGlyph.jsx'

const eyebrow = 'text-[11px] font-medium tracking-wide text-slate-500 uppercase'

function Header({ label, title, subtitle, onClear }) {
  return (
    <div className="flex items-start justify-between gap-3">
      <div className="min-w-0">
        <p className={eyebrow}>{label}</p>
        <h2 className="mt-1 text-base leading-snug font-semibold text-slate-900">{title}</h2>
        {subtitle && <p className="mt-0.5 font-mono text-xs text-slate-600">{subtitle}</p>}
      </div>
      <Button variant="ghost" size="sm" onClick={onClear} aria-label="Clear selection" className="-mt-1 -mr-2 w-8 px-0">
        <svg width="12" height="12" viewBox="0 0 12 12" aria-hidden="true">
          <path d="M2 2l8 8M10 2l-8 8" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" />
        </svg>
      </Button>
    </div>
  )
}

function Field({ label, children }) {
  return (
    <div>
      <dt className="text-xs text-slate-500">{label}</dt>
      <dd className="mt-1 text-sm text-slate-900">{children}</dd>
    </div>
  )
}

function LocationDetails({ index, location, onSelect }) {
  const roads = [...index.roadsByLocation.get(location.id)].sort((a, b) => a.distance_km - b.distance_km)
  const stacked = coincidentCount(index, location)

  return (
    <div className="space-y-5">
      <Header label="Location" title={location.name} subtitle={location.code} onClear={() => onSelect(null)} />
      <dl className="grid grid-cols-2 gap-4">
        <Field label="Type">
          <KindBadge kind={location.kind} />
        </Field>
        <Field label="Coordinates">
          <span className="font-mono text-[13px] tabular-nums">
            x {formatCoord(location.x)} · y {formatCoord(location.y)}
          </span>
        </Field>
      </dl>
      {stacked > 0 && (
        <p className="rounded-md bg-stone-100 px-3 py-2 text-xs text-slate-700">
          Shares these coordinates with {stacked} other {stacked === 1 ? 'location' : 'locations'}. They are
          fanned out slightly on the map so each one can be selected.
        </p>
      )}
      <section aria-labelledby="inspector-roads">
        <h3 id="inspector-roads" className={eyebrow}>
          Connected roads ({roads.length})
        </h3>
        {roads.length === 0 ? (
          <p className="mt-2 flex flex-wrap items-center gap-2 text-sm text-slate-600">
            <IsolatedBadge /> No road connects this location yet.
          </p>
        ) : (
          <ul className="mt-2 divide-y divide-stone-100 overflow-hidden rounded-md border border-stone-200">
            {roads.map((road) => {
              const otherId = road.from_id === location.id ? road.to_id : road.from_id
              const relation = road.is_one_way ? (road.from_id === location.id ? 'Outbound' : 'Inbound') : 'Two-way'
              return (
                <li key={road.id}>
                  <button
                    type="button"
                    onClick={() => onSelect({ type: 'road', id: road.id })}
                    aria-label={`Select road to ${locationName(index, otherId)}: ${describeRoad(index, road)}`}
                    className="flex w-full items-center justify-between gap-3 px-3 py-2.5 text-left hover:bg-stone-50 focus-visible:-outline-offset-2"
                  >
                    <span className="min-w-0">
                      <span className="flex items-center gap-2 text-sm font-medium text-slate-900">
                        <KindIcon kind={index.byId.get(otherId)?.kind} size={12} />
                        <span className="truncate">{locationName(index, otherId)}</span>
                      </span>
                      <span className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1">
                        <DirectionLabel oneWay={road.is_one_way} relation={relation} />
                        {road.is_closed && <RoadStatusBadge closed />}
                      </span>
                    </span>
                    <span className="shrink-0 font-mono text-sm text-slate-700 tabular-nums">
                      {formatKm(road.distance_km)}
                    </span>
                  </button>
                </li>
              )
            })}
          </ul>
        )}
      </section>
    </div>
  )
}

function Endpoint({ index, id, role, onSelect }) {
  const location = index.byId.get(id)
  return (
    <button
      type="button"
      onClick={() => onSelect({ type: 'location', id })}
      aria-label={`Select ${role.toLowerCase()} location ${locationName(index, id)}`}
      className="flex w-full items-center gap-3 rounded-md border border-stone-200 px-3 py-2 text-left hover:bg-stone-50"
    >
      <KindIcon kind={location?.kind} />
      <span className="min-w-0">
        <span className="block text-[11px] text-slate-500">{role}</span>
        <span className="block truncate text-sm font-medium text-slate-900">{locationName(index, id)}</span>
      </span>
      <span className="ml-auto font-mono text-xs text-slate-500">{locationCode(index, id)}</span>
    </button>
  )
}

function RoadDetails({ index, road, onSelect }) {
  const arrow = road.is_one_way ? '→' : '↔'
  return (
    <div className="space-y-5">
      <Header
        label={`Road #${road.id}`}
        title={`${locationName(index, road.from_id)} ${arrow} ${locationName(index, road.to_id)}`}
        onClear={() => onSelect(null)}
      />
      <div className="space-y-1.5">
        <Endpoint index={index} id={road.from_id} role={road.is_one_way ? 'From' : 'Endpoint A'} onSelect={onSelect} />
        <div className="flex justify-center text-slate-500" aria-hidden="true">
          <svg width="12" height="16" viewBox="0 0 12 16">
            <path
              d={road.is_one_way ? 'M6 1v12M2.5 9.5L6 13l3.5-3.5' : 'M6 3v10M2.5 6.5L6 3l3.5 3.5M2.5 9.5L6 13l3.5-3.5'}
              fill="none"
              stroke="currentColor"
              strokeWidth="1.6"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        </div>
        <Endpoint index={index} id={road.to_id} role={road.is_one_way ? 'To' : 'Endpoint B'} onSelect={onSelect} />
      </div>
      <dl className="grid grid-cols-3 gap-4">
        <Field label="Distance">
          <span className="font-mono tabular-nums">{formatKm(road.distance_km)}</span>
        </Field>
        <Field label="Direction">
          <DirectionLabel oneWay={road.is_one_way} />
        </Field>
        <Field label="Status">
          <RoadStatusBadge closed={road.is_closed} />
        </Field>
      </dl>
    </div>
  )
}

function Overview({ index, onSelect }) {
  const summary = networkSummary(index)
  const rows = ['DEPOT', 'HUB', 'CUSTOMER'].map((kind) => ({
    key: kind,
    label: kindMeta(kind).plural,
    icon: <KindIcon kind={kind} />,
    value: summary.byKind[kind] ?? 0,
  }))

  return (
    <div className="space-y-5">
      <div>
        <h2 className="text-sm font-semibold text-slate-900">Network overview</h2>
        <p className="mt-1 text-sm text-slate-600">Select a location or road on the map to see its details.</p>
      </div>
      <dl className="divide-y divide-stone-100 rounded-md border border-stone-200 text-sm">
        {rows.map((row) => (
          <div key={row.key} className="flex items-center justify-between px-3 py-2">
            <dt className="flex items-center gap-2 text-slate-700">
              {row.icon}
              {row.label}
            </dt>
            <dd className="font-mono text-slate-900 tabular-nums">{row.value}</dd>
          </div>
        ))}
        <div className="flex items-center justify-between px-3 py-2">
          <dt className="text-slate-700">Roads</dt>
          <dd className="font-mono text-slate-900 tabular-nums">{summary.roads}</dd>
        </div>
        <div className="flex items-center justify-between px-3 py-2">
          <dt>
            <DirectionLabel oneWay />
          </dt>
          <dd className="font-mono text-slate-900 tabular-nums">{summary.oneWay}</dd>
        </div>
        <div className="flex items-center justify-between px-3 py-2">
          <dt>
            <RoadStatusBadge closed />
          </dt>
          <dd className="font-mono text-slate-900 tabular-nums">{summary.closed}</dd>
        </div>
      </dl>
      {summary.isolated.length > 0 && (
        <section aria-labelledby="inspector-isolated">
          <h3 id="inspector-isolated" className={eyebrow}>
            Not connected ({summary.isolated.length})
          </h3>
          <ul className="mt-2 space-y-1">
            {summary.isolated.map((location) => (
              <li key={location.id}>
                <button
                  type="button"
                  onClick={() => onSelect({ type: 'location', id: location.id })}
                  className="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm text-slate-800 hover:bg-stone-100"
                >
                  <KindIcon kind={location.kind} size={12} />
                  <span className="truncate">{location.name}</span>
                  <span className="ml-auto font-mono text-xs text-slate-500">{location.code}</span>
                </button>
              </li>
            ))}
          </ul>
        </section>
      )}
      {index.unknownRoads.length > 0 && (
        <p className="rounded-md bg-closed-50 px-3 py-2 text-xs text-closed">
          {index.unknownRoads.length} road(s) reference locations that were not returned, so they are not drawn.
        </p>
      )}
      <p className="hidden text-xs leading-relaxed text-slate-500 lg:block">
        Keyboard: <kbd className="font-mono">Tab</kbd> moves between locations, <kbd className="font-mono">Enter</kbd>{' '}
        selects, <kbd className="font-mono">Esc</kbd> clears. Roads are reachable from a selected location.
      </p>
    </div>
  )
}

/** Side panel: overview when nothing is selected, otherwise location or road details. */
export function MapInspector({ index, selection, onSelect }) {
  if (selection?.type === 'location') {
    const location = index.byId.get(selection.id)
    if (location) return <LocationDetails index={index} location={location} onSelect={onSelect} />
  }
  if (selection?.type === 'road') {
    const road = index.roads.find((r) => r.id === selection.id)
    if (road) return <RoadDetails index={index} road={road} onSelect={onSelect} />
  }
  return <Overview index={index} onSelect={onSelect} />
}
