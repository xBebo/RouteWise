import { formatKm, locationName } from '../../lib/network.js'
import { formatDateTime, formatEta, humanizeWarning, pathNames, visitedName } from '../../lib/route.js'

const th = 'px-3 py-2 text-left text-xs font-medium text-slate-500'
const td = 'px-3 py-2 align-top'

function Stat({ label, value, detail }) {
  return (
    <div className="min-w-0">
      <dt className="text-[11px] font-medium tracking-wide text-slate-500 uppercase">{label}</dt>
      <dd className="text-xl font-semibold tracking-tight text-slate-900 tabular-nums">{value}</dd>
      {detail && <dd className="text-xs text-slate-500">{detail}</dd>}
    </div>
  )
}

function StopNumber({ n }) {
  return (
    <span className="inline-flex size-5 shrink-0 items-center justify-center rounded-full bg-accent-600 text-[10px] font-semibold text-white tabular-nums">
      {n}
    </span>
  )
}

/**
 * Renders one route exactly as the API returned it (preview or saved).
 * `actions` is an optional slot (e.g. the Save button); `heading` names the block.
 */
export function RouteResult({ route, index, heading = 'Route', actions }) {
  const isRun = route.mode === 'RUN'
  const stopNumber = new Map(route.ordered_stops.map((id, i) => [id, i + 1]))
  const names = pathNames(route)
  const skipped = route.unreachable_stops // absent on saved routes: not persisted
  const sameOrigin = route.legs.length === 0
  // The skipped-stops warning repeats the named "Skipped" line below, so drop it when that line shows.
  const warnings = route.warnings.filter((w) => !(skipped?.length && w.startsWith('Unreachable stop(s) skipped')))

  return (
    <section aria-labelledby="route-result-title" className="space-y-4 p-4 sm:p-5">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <h2 id="route-result-title" className="text-sm font-semibold text-slate-900">
            {heading}
          </h2>
          <p className="mt-0.5 flex flex-wrap items-center gap-1.5 text-xs text-slate-600">
            <span
              className={`rounded px-1.5 py-0.5 font-medium ${
                isRun ? 'bg-amber-50 text-amber-800 ring-1 ring-amber-200 ring-inset' : 'bg-accent-50 text-accent-700'
              }`}
            >
              {isRun ? 'Heuristic' : 'Optimal'}
            </span>
            {route.label}
          </p>
          {route.id != null && (
            <p className="mt-1 text-xs text-slate-500">
              Saved route #{route.id} · {formatDateTime(route.created_at)}
            </p>
          )}
        </div>
        {actions}
      </div>

      <dl className="grid grid-cols-2 gap-3 rounded-lg border border-stone-200 bg-stone-50 px-4 py-3">
        <Stat label="Distance" value={formatKm(route.total_km)} />
        <Stat label="ETA" value={formatEta(route.eta_minutes)} detail={`at ${route.avg_speed_kmh.toLocaleString()} km/h`} />
      </dl>

      {warnings.length > 0 && (
        <ul className="space-y-1 rounded-md border border-closed/30 bg-closed-50 px-3 py-2 text-sm text-closed">
          {warnings.map((warning) => (
            <li key={warning}>{humanizeWarning(warning, (id) => locationName(index, id))}</li>
          ))}
        </ul>
      )}

      {isRun && (
        <div className="space-y-2">
          <h3 className="text-xs font-semibold text-slate-700">Visiting order</h3>
          <ol className="space-y-1 text-sm">
            {route.ordered_stops.map((id, i) => (
              <li key={id} className="flex items-center gap-2">
                <StopNumber n={i + 1} />
                {visitedName(route, id)}
              </li>
            ))}
          </ol>
          {route.returned_to_depot && <p className="text-xs text-slate-600">Returns to {route.origin_name} at the end.</p>}
          {Array.isArray(skipped) ? (
            skipped.length > 0 && (
              <p className="rounded-md border border-closed/30 bg-closed-50 px-3 py-2 text-sm text-closed">
                <span className="font-semibold">Skipped, no open route:</span>{' '}
                {skipped.map((id) => locationName(index, id)).join(', ')}
              </p>
            )
          ) : (
            <p className="text-xs text-slate-500">
              Skipped stops aren’t stored with saved routes, so this view can’t show whether any were skipped.
            </p>
          )}
        </div>
      )}

      <div>
        <h3 className="mb-1 text-xs font-semibold text-slate-700">Path</h3>
        <p className="text-sm text-slate-800">
          {sameOrigin ? `${names[0]} (origin and destination are the same, no travel needed)` : names.join(' → ')}
        </p>
      </div>

      {!sameOrigin && (
        <div className="overflow-x-auto rounded-lg border border-stone-200">
          <table className="w-full text-sm">
            <caption className="sr-only">Legs in travel order with leg distance and cumulative distance</caption>
            <thead className="bg-stone-50">
              <tr>
                <th scope="col" className={th}>#</th>
                <th scope="col" className={th}>Leg</th>
                <th scope="col" className={`${th} text-right`}>Distance</th>
                <th scope="col" className={`${th} text-right`}>Cumulative</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-stone-100">
              {route.legs.map((leg) => (
                <tr key={leg.seq}>
                  <td className={`${td} text-xs text-slate-500 tabular-nums`}>{leg.seq}</td>
                  <td className={td}>
                    <span className="text-slate-600">{leg.from_name}</span>
                    <span aria-hidden="true" className="text-slate-400"> → </span>
                    <span className="sr-only"> to </span>
                    <span className="font-medium text-slate-900">{leg.to_name}</span>
                    {leg.is_delivery_stop && (
                      <span className="ml-1.5 inline-flex items-center gap-1 align-middle text-xs text-accent-700">
                        <StopNumber n={stopNumber.get(leg.to_id)} />
                        <span className="sr-only">delivery stop {stopNumber.get(leg.to_id)}</span>
                      </span>
                    )}
                  </td>
                  <td className={`${td} text-right font-mono whitespace-nowrap text-slate-700 tabular-nums`}>{formatKm(leg.km)}</td>
                  <td className={`${td} text-right font-mono whitespace-nowrap text-slate-900 tabular-nums`}>
                    {formatKm(leg.cumulative_km)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}
