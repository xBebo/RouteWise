import { useState } from 'react'
import { DirectionLabel, IsolatedBadge, KindBadge, RoadStatusBadge } from '../components/Badges.jsx'
import { Button } from '../components/Button.jsx'
import { PageHeader } from '../components/PageHeader.jsx'
import { SearchInput } from '../components/SearchInput.jsx'
import { StatusMessage } from '../components/StatusMessage.jsx'
import { countsLabel, formatCoord, formatKm, locationCode, locationName, sortLocations } from '../lib/network.js'

const th = 'px-4 py-2.5 text-left text-xs font-medium text-slate-500'
const td = 'px-4 py-2.5 align-middle'

function MapButton({ label, onClick }) {
  return (
    <Button variant="ghost" size="sm" onClick={onClick} aria-label={label} title={label} className="text-accent-700">
      <svg width="14" height="14" viewBox="0 0 20 20" aria-hidden="true">
        <path d="M4 13l5-8 6 6" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinejoin="round" />
        <circle cx="4" cy="13" r="2.2" fill="currentColor" />
        <circle cx="9" cy="5" r="2.2" fill="currentColor" />
        <circle cx="15" cy="11" r="2.2" fill="currentColor" />
      </svg>
      <span className="hidden sm:inline">Map</span>
    </Button>
  )
}

function Section({ id, title, count, total, children }) {
  return (
    <section aria-labelledby={id} className="overflow-hidden rounded-lg border border-stone-200 bg-white">
      <div className="flex items-baseline justify-between gap-3 border-b border-stone-200 px-4 py-3">
        <h2 id={id} className="text-sm font-semibold text-slate-900">
          {title}
        </h2>
        <p className="text-xs text-slate-500 tabular-nums">
          {count === total ? `${total} total` : `${count} of ${total} shown`}
        </p>
      </div>
      {children}
    </section>
  )
}

function LocationsView({ index, locations, onShowOnMap }) {
  const roadCount = (id) => index.roadsByLocation.get(id).length
  const show = (location) => onShowOnMap({ type: 'location', id: location.id })

  return (
    <>
      <table className="hidden w-full text-sm md:table">
        <caption className="sr-only">Locations with code, name, type, coordinates and connected roads</caption>
        <thead className="bg-stone-50">
          <tr>
            <th scope="col" className={th}>Code</th>
            <th scope="col" className={th}>Name</th>
            <th scope="col" className={th}>Type</th>
            <th scope="col" className={`${th} text-right`}>X</th>
            <th scope="col" className={`${th} text-right`}>Y</th>
            <th scope="col" className={th}>Roads</th>
            <th scope="col" className={th}><span className="sr-only">Actions</span></th>
          </tr>
        </thead>
        <tbody className="divide-y divide-stone-100">
          {locations.map((location) => (
            <tr key={location.id} className="hover:bg-stone-50">
              <td className={`${td} font-mono text-xs text-slate-600`}>{location.code}</td>
              <th scope="row" className={`${td} text-left font-medium text-slate-900`}>{location.name}</th>
              <td className={td}><KindBadge kind={location.kind} /></td>
              <td className={`${td} text-right font-mono text-slate-700 tabular-nums`}>{formatCoord(location.x)}</td>
              <td className={`${td} text-right font-mono text-slate-700 tabular-nums`}>{formatCoord(location.y)}</td>
              <td className={td}>
                {index.isolated.has(location.id) ? (
                  <IsolatedBadge />
                ) : (
                  <span className="font-mono text-slate-700 tabular-nums">{roadCount(location.id)}</span>
                )}
              </td>
              <td className={`${td} py-1 text-right`}>
                <MapButton label={`Show ${location.name} on map`} onClick={() => show(location)} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      <ul className="divide-y divide-stone-100 md:hidden">
        {locations.map((location) => (
          <li key={location.id} className="flex items-start justify-between gap-3 px-4 py-3">
            <div className="min-w-0 space-y-1.5">
              <p className="flex flex-wrap items-baseline gap-x-2">
                <span className="font-medium text-slate-900">{location.name}</span>
                <span className="font-mono text-xs text-slate-500">{location.code}</span>
              </p>
              <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5 text-xs text-slate-600">
                <KindBadge kind={location.kind} />
                <span className="font-mono tabular-nums">
                  x {formatCoord(location.x)} · y {formatCoord(location.y)}
                </span>
                {index.isolated.has(location.id) ? (
                  <IsolatedBadge />
                ) : (
                  <span>
                    {roadCount(location.id)} {roadCount(location.id) === 1 ? 'road' : 'roads'}
                  </span>
                )}
              </div>
            </div>
            <MapButton label={`Show ${location.name} on map`} onClick={() => show(location)} />
          </li>
        ))}
      </ul>
    </>
  )
}

function Endpoint({ index, id }) {
  return (
    <span className="block min-w-0">
      <span className="block font-medium text-slate-900">{locationName(index, id)}</span>
      <span className="block font-mono text-xs text-slate-500">{locationCode(index, id)}</span>
    </span>
  )
}

function RoadsView({ index, roads, onShowOnMap }) {
  const show = (road) => onShowOnMap({ type: 'road', id: road.id })
  const label = (road) =>
    `Show road ${locationName(index, road.from_id)} to ${locationName(index, road.to_id)} on map`

  return (
    <>
      <table className="hidden w-full text-sm md:table">
        <caption className="sr-only">Roads with endpoints, distance, direction and status</caption>
        <thead className="bg-stone-50">
          <tr>
            <th scope="col" className={th}>From</th>
            <th scope="col" className={th}>Direction</th>
            <th scope="col" className={th}>To</th>
            <th scope="col" className={`${th} text-right`}>Distance</th>
            <th scope="col" className={th}>Status</th>
            <th scope="col" className={th}><span className="sr-only">Actions</span></th>
          </tr>
        </thead>
        <tbody className="divide-y divide-stone-100">
          {roads.map((road) => (
            <tr key={road.id} className={road.is_closed ? 'bg-closed-50/40' : 'hover:bg-stone-50'}>
              <td className={td}><Endpoint index={index} id={road.from_id} /></td>
              <td className={td}><DirectionLabel oneWay={road.is_one_way} /></td>
              <td className={td}><Endpoint index={index} id={road.to_id} /></td>
              <td className={`${td} text-right font-mono text-slate-800 tabular-nums`}>{formatKm(road.distance_km)}</td>
              <td className={td}><RoadStatusBadge closed={road.is_closed} /></td>
              <td className={`${td} py-1 text-right`}>
                <MapButton label={label(road)} onClick={() => show(road)} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      <ul className="divide-y divide-stone-100 md:hidden">
        {roads.map((road) => (
          <li key={road.id} className="flex items-start justify-between gap-3 px-4 py-3">
            <div className="min-w-0 space-y-1.5">
              <p className="font-medium text-slate-900">
                {locationName(index, road.from_id)}{' '}
                <span className="text-slate-400" aria-hidden="true">{road.is_one_way ? '→' : '↔'}</span>
                <span className="sr-only">{road.is_one_way ? ' to ' : ' and '}</span>{' '}
                {locationName(index, road.to_id)}
              </p>
              <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5">
                <span className="font-mono text-xs text-slate-800 tabular-nums">{formatKm(road.distance_km)}</span>
                <DirectionLabel oneWay={road.is_one_way} />
                <RoadStatusBadge closed={road.is_closed} />
              </div>
            </div>
            <MapButton label={label(road)} onClick={() => show(road)} />
          </li>
        ))}
      </ul>
    </>
  )
}

export function DirectoryPage({ index, onShowOnMap }) {
  const [query, setQuery] = useState('')
  const term = query.trim().toLowerCase()
  const matches = (location) =>
    !!location && (location.name.toLowerCase().includes(term) || location.code.toLowerCase().includes(term))

  const locations = sortLocations(index.locations).filter((l) => !term || matches(l))
  const roads = index.roads.filter(
    (road) => !term || matches(index.byId.get(road.from_id)) || matches(index.byId.get(road.to_id)),
  )

  const noMatches = (what) => (
    <StatusMessage tone="empty" compact title={`No ${what} match “${query.trim()}”`}>
      <button type="button" className="font-medium text-accent-700 underline underline-offset-2" onClick={() => setQuery('')}>
        Clear search
      </button>
    </StatusMessage>
  )

  return (
    <div className="flex-1">
      <PageHeader title="Locations & Roads" meta={`${countsLabel(index.locations.length, index.roads.length)} · read-only`}>
        <SearchInput
          id="directory-search"
          label="Filter locations and roads by name or code"
          value={query}
          onChange={setQuery}
          placeholder="Filter by name or code"
        />
      </PageHeader>

      <div className="mx-auto max-w-6xl space-y-6 p-4 sm:p-6">
        <Section id="locations-title" title="Locations" count={locations.length} total={index.locations.length}>
          {index.locations.length === 0 ? (
            <StatusMessage tone="empty" compact title="No locations yet">
              Seed the sample network or add locations through the API.
            </StatusMessage>
          ) : locations.length === 0 ? (
            noMatches('locations')
          ) : (
            <LocationsView index={index} locations={locations} onShowOnMap={onShowOnMap} />
          )}
        </Section>

        <Section id="roads-title" title="Roads" count={roads.length} total={index.roads.length}>
          {index.roads.length === 0 ? (
            <StatusMessage tone="empty" compact title="No roads yet">
              Roads appear here once locations are connected.
            </StatusMessage>
          ) : roads.length === 0 ? (
            noMatches('roads')
          ) : (
            <RoadsView index={index} roads={roads} onShowOnMap={onShowOnMap} />
          )}
        </Section>
      </div>
    </div>
  )
}
