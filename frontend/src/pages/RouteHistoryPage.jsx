import { useEffect, useState } from 'react'
import { PageHeader } from '../components/PageHeader.jsx'
import { StatusMessage } from '../components/StatusMessage.jsx'
import { RouteResult } from '../components/route/RouteResult.jsx'
import { RouteWorkspace } from '../components/route/RouteWorkspace.jsx'
import { hrefFor } from '../hooks/useHashRoute.js'
import { formatKm } from '../lib/network.js'
import { formatDateTime, formatEta, routeHeadline, visitedName } from '../lib/route.js'
import { getRoute, getRoutes } from '../services/api.js'

/**
 * Loads `load(signal)` whenever `deps` change. Loading is derived (the stored
 * result belongs to other deps), so no state is set synchronously in the effect.
 */
function useRequest(load, deps) {
  const depsKey = JSON.stringify(deps)
  const [state, setState] = useState(null) // { depsKey, data?, error? }
  useEffect(() => {
    const controller = new AbortController()
    load(controller.signal)
      .then((data) => setState({ depsKey, data }))
      .catch((error) => {
        if (!controller.signal.aborted) setState({ depsKey, error })
      })
    return () => controller.abort()
    // eslint-disable-next-line react-hooks/exhaustive-deps -- `load` is re-created each render; deps drive the reload
  }, [depsKey])
  return state?.depsKey === depsKey ? state : { loading: true }
}

function ModeBadge({ mode }) {
  return (
    <span className="rounded bg-stone-100 px-1.5 py-0.5 text-[11px] font-medium text-slate-700">
      {mode === 'RUN' ? 'Multi-stop' : 'Point'}
    </span>
  )
}

function stopsText(route) {
  if (route.mode === 'RUN') return route.ordered_stops.map((id) => visitedName(route, id)).join(' → ')
  return null
}

function HistoryList({ list, onRetry }) {
  if (list.loading) {
    return (
      <StatusMessage tone="loading" title="Loading saved routes…" compact />
    )
  }
  if (list.error) {
    return (
      <StatusMessage tone="error" title="Couldn’t load route history" onRetry={onRetry} compact>
        {list.error.message}
      </StatusMessage>
    )
  }
  if (!list.data.length) {
    return (
      <StatusMessage tone="empty" title="No saved routes yet" compact>
        <p>
          Plan a route in the <a href={hrefFor('planner')} className="font-medium text-accent-700 underline">Route Planner</a> and
          save it to see it here.
        </p>
      </StatusMessage>
    )
  }
  return (
    <ul className="divide-y divide-stone-100" aria-label="Saved routes, newest first">
      {list.data.map((route) => (
        <li key={route.id}>
          <a href={hrefFor(`history/${route.id}`)} className="block px-4 py-3 hover:bg-stone-50 sm:px-5">
            <span className="flex items-center justify-between gap-2 text-xs text-slate-500">
              <span className="flex items-center gap-2">
                <ModeBadge mode={route.mode} />#{route.id}
              </span>
              <time dateTime={route.created_at}>{formatDateTime(route.created_at)}</time>
            </span>
            <span className="mt-1 block text-sm font-medium text-slate-900">{routeHeadline(route)}</span>
            {stopsText(route) && <span className="block truncate text-xs text-slate-600">{stopsText(route)}</span>}
            <span className="mt-1 flex gap-3 font-mono text-xs text-slate-700 tabular-nums">
              <span>{formatKm(route.total_km)}</span>
              <span>{formatEta(route.eta_minutes)}</span>
            </span>
          </a>
        </li>
      ))}
    </ul>
  )
}

export function RouteHistoryPage({ index, routeId }) {
  const [attempt, setAttempt] = useState(0)
  const list = useRequest((signal) => getRoutes(signal), [attempt])
  const detail = useRequest((signal) => (routeId ? getRoute(routeId, signal) : Promise.resolve(null)), [routeId, attempt])
  const route = routeId && detail.data ? detail.data : null
  const retry = () => setAttempt((n) => n + 1)

  let controls
  let result = null
  if (!routeId) {
    controls = (
      <>
        <h2 className="px-4 pt-4 text-sm font-semibold text-slate-900 sm:px-5">Saved routes</h2>
        <HistoryList list={list} onRetry={retry} />
      </>
    )
  } else {
    controls = (
      <div className="px-4 py-3 sm:px-5">
        <a href={hrefFor('history')} className="text-sm font-medium text-accent-700 hover:underline">
          ← All saved routes
        </a>
      </div>
    )
    if (detail.loading) {
      result = <StatusMessage tone="loading" title={`Loading route #${routeId}…`} compact />
    } else if (detail.error) {
      result =
        detail.error.status === 404 ? (
          <StatusMessage tone="empty" title={`Route #${routeId} not found`} compact>
            It may belong to a different database.
          </StatusMessage>
        ) : (
          <StatusMessage tone="error" title="Couldn’t load this route" onRetry={retry} compact>
            {detail.error.message}
          </StatusMessage>
        )
    } else {
      result = (
        <>
          <RouteResult
            route={route}
            index={index}
            heading={<span className="flex items-center gap-2"><ModeBadge mode={route.mode} />{routeHeadline(route)}</span>}
          />
          <p className="px-4 pb-4 text-xs text-slate-500 sm:px-5">
            Shown as saved. Later road closures or edits don’t change this route; the map draws it between the saved
            locations at their current positions.
          </p>
        </>
      )
    }
  }

  return (
    <div className="flex flex-1 flex-col lg:min-h-0">
      <PageHeader
        title="Route History"
        meta={list.data ? `${list.data.length} saved ${list.data.length === 1 ? 'route' : 'routes'}` : 'Saved routes'}
      />
      <RouteWorkspace index={index} route={route} controls={controls} result={result} />
    </div>
  )
}
