import { useEffect, useState } from 'react'

export const ROUTES = ['map', 'directory', 'planner', 'history']

/** '#/history/12' -> 'history/12'; unknown pages fall back to 'map'. */
function readRoute() {
  const path = window.location.hash.replace(/^#\/?/, '')
  const [page, param] = path.split('/')
  if (!ROUTES.includes(page)) return 'map'
  return page === 'history' && /^\d+$/.test(param ?? '') ? `history/${param}` : page
}

/**
 * Tiny hash router: '#/map', '#/directory', '#/planner', '#/history[/<id>]'.
 * Returns the path string; back/forward and deep links work.
 */
export function useHashRoute() {
  const [route, setRoute] = useState(readRoute)

  useEffect(() => {
    const onChange = () => setRoute(readRoute())
    window.addEventListener('hashchange', onChange)
    return () => window.removeEventListener('hashchange', onChange)
  }, [])

  return route
}

export const hrefFor = (route) => `#/${route}`
