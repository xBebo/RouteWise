// All HTTP access to the Flask backend lives here.
// Requests use relative /api URLs; in development Vite proxies them to Flask
// (see vite.config.js), so the browser never needs Flask's address.

export class ApiError extends Error {
  constructor(message, status, body = null) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.body = body // Flask error JSON: { error, fields?, ...details }
  }
}

const UNREACHABLE =
  'Can’t reach the RouteWise API. Check that Flask is running on 127.0.0.1:5000.'

async function fetchList(key, signal) {
  let response
  try {
    response = await fetch(`/api/${key}`, { signal, headers: { Accept: 'application/json' } })
  } catch (error) {
    if (error.name === 'AbortError') throw error
    throw new ApiError(UNREACHABLE)
  }

  // Flask errors are JSON ({ error }); the Vite proxy answers with a plain 5xx when Flask is down.
  const body = await response.json().catch(() => null)

  if (!response.ok) {
    const message = body?.error ?? (response.status >= 500 ? UNREACHABLE : `Request failed (${response.status}).`)
    throw new ApiError(message, response.status)
  }
  if (!Array.isArray(body?.[key])) {
    throw new ApiError(`Unexpected response from /api/${key}.`, response.status)
  }
  return body[key]
}

export const getLocations = (signal) => fetchList('locations', signal)
export const getRoads = (signal) => fetchList('roads', signal)

/** Loads both datasets in parallel; fails if either request fails. */
export async function getNetwork(signal) {
  const [locations, roads] = await Promise.all([getLocations(signal), getRoads(signal)])
  return { locations, roads }
}
/** JSON request for the route endpoints; resolves to body.route / body.routes, throws ApiError. */
async function requestRoute(path, { method = 'GET', body, signal } = {}) {
  let response
  try {
    response = await fetch(`/api/${path}`, {
      method,
      signal,
      headers: { Accept: 'application/json', ...(body && { 'Content-Type': 'application/json' }) },
      ...(body && { body: JSON.stringify(body) }),
    })
  } catch (error) {
    if (error.name === 'AbortError') throw error
    throw new ApiError(UNREACHABLE)
  }
  const data = await response.json().catch(() => null)
  if (!response.ok) {
    const message = data?.error ?? (response.status >= 500 ? UNREACHABLE : `Request failed (${response.status}).`)
    throw new ApiError(message, response.status, data)
  }
  const result = data?.route ?? data?.routes
  if (!result) throw new ApiError(`Unexpected response from /api/${path}.`, response.status)
  return result
}

export const planPointRoute = (body, signal) => requestRoute('routes/point', { method: 'POST', body, signal })
export const planDeliveryRun = (body, signal) => requestRoute('routes/run', { method: 'POST', body, signal })
export const saveRoute = (body) => requestRoute('routes', { method: 'POST', body })
export const getRoutes = (signal) => requestRoute('routes', { signal })
export const getRoute = (id, signal) => requestRoute(`routes/${id}`, { signal })

export async function requestNetwork(path, method = 'GET', body) {
  const response = await fetch('/api/' + path, {
    method,
    ...(body === undefined ? {} : {
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),
  })
  const data = await response.json().catch(() => null)
  if (!response.ok || !data) {
    const details = Object.values(data?.fields ?? {}).join(' ')
    throw new Error([data?.error ?? 'Could not reach the RouteWise API.', details].filter(Boolean).join(' '))
  }
  return data
}
