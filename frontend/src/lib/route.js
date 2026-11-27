// Pure helpers for route results returned by the Flask API (preview or saved).
// The backend owns the calculation; these only shape it for display. Values are
// rounded here for display only, never written back.

export const MAX_STOPS = 8

export function formatEta(minutes) {
  if (!Number.isFinite(minutes)) return '—'
  if (minutes === 0) return '0 min'
  if (minutes < 1) return '< 1 min'
  const total = Math.round(minutes)
  const hours = Math.floor(total / 60)
  const rest = total % 60
  return hours ? `${hours} h ${String(rest).padStart(2, '0')} min` : `${rest} min`
}

export function formatDateTime(iso) {
  const date = new Date(iso)
  return Number.isNaN(date.getTime())
    ? iso ?? '—'
    : date.toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })
}

/** Location names along the path, taken from the route's own legs (snapshots for saved routes). */
export function pathNames(route) {
  return [route.origin_name, ...route.legs.map((leg) => leg.to_name)]
}

/** Name of a location the route visits, falling back to its id. */
export function visitedName(route, id) {
  if (id === route.origin_id) return route.origin_name
  return route.legs.find((leg) => leg.to_id === id)?.to_name ?? `Location #${id}`
}

/** "Depot D → Node B" for POINT, "Depot D · 3 stops" for RUN. */
export function routeHeadline(route) {
  if (route.mode === 'RUN') {
    const count = route.ordered_stops.length
    return `${route.origin_name} · ${count} ${count === 1 ? 'stop' : 'stops'}`
  }
  return route.destination_id === route.origin_id
    ? `${route.origin_name} (same origin)`
    : `${route.origin_name} → ${visitedName(route, route.destination_id)}`
}

/**
 * Map markers: S on the origin, E on a POINT destination (unless it is the
 * origin), and 1..n on RUN delivery stops in the backend's visiting order.
 */
export function routeMarkers(route) {
  const markers = [{ id: route.origin_id, text: 'S', tone: 'start' }]
  if (route.mode === 'RUN') {
    route.ordered_stops.forEach((id, i) => markers.push({ id, text: String(i + 1), tone: 'stop' }))
  } else if (route.destination_id !== route.origin_id) {
    markers.push({ id: route.destination_id, text: 'E', tone: 'end' })
  }
  return markers
}

/**
 * Backend warnings name locations by id ("skipped: [20]", "from stop 13 to depot 1").
 * Swap those ids for names; any other text passes through unchanged.
 */
export function humanizeWarning(text, nameOf) {
  return text
    .replace(/\[(\d+(?:, \d+)*)\]/g, (_, ids) => ids.split(', ').map((id) => nameOf(Number(id))).join(', '))
    .replace(/\b(stop|depot) (\d+)\b/g, (_, word, id) => `${word} ${nameOf(Number(id))}`)
}

/** Accessible one-line description of the planned path. */
export function routeSummaryText(route) {
  const names = pathNames(route)
  const distance = `${route.total_km.toLocaleString(undefined, { maximumFractionDigits: 1 })} km`
  return names.length === 1
    ? `Route starts and ends at ${names[0]}, 0 km.`
    : `Route ${names.join(' to ')}, ${distance}, ${formatEta(route.eta_minutes)}.`
}
