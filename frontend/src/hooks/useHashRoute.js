import { useEffect, useState } from 'react'

export const ROUTES = ['map', 'directory']

function readRoute() {
  const name = window.location.hash.replace(/^#\/?/, '')
  return ROUTES.includes(name) ? name : 'map'
}

/** Tiny hash router: '#/map' or '#/directory'. Back/forward and deep links work. */
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
