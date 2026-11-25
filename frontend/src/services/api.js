// All HTTP access to the Flask backend lives here.
// Requests use relative /api URLs; in development Vite proxies them to Flask
// (see vite.config.js), so the browser never needs Flask's address.

export class ApiError extends Error {
  constructor(message, status) {
    super(message)
    this.name = 'ApiError'
    this.status = status
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
