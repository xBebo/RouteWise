import { useEffect, useMemo, useRef, useState } from 'react'
import { AppShell } from './components/AppShell.jsx'
import { PageHeader } from './components/PageHeader.jsx'
import { StatusMessage } from './components/StatusMessage.jsx'
import { hrefFor, useHashRoute } from './hooks/useHashRoute.js'
import { useNetwork } from './hooks/useNetwork.js'
import { buildIndex } from './lib/network.js'
import { DirectoryPage } from './pages/DirectoryPage.jsx'
import { NetworkMapPage } from './pages/NetworkMapPage.jsx'

const TITLES = { map: 'Network Map', directory: 'Locations & Roads' }

export default function App() {
  // One request for both datasets, shared by every screen.
  const network = useNetwork()
  const route = useHashRoute()
  const [selection, setSelection] = useState(null) // { type: 'location' | 'road', id } | null

  const index = useMemo(
    () => (network.data ? buildIndex(network.data.locations, network.data.roads) : null),
    [network.data],
  )

  // Move focus to the new page title after navigation (not on first load).
  const previousRoute = useRef(route)
  useEffect(() => {
    if (previousRoute.current !== route) document.getElementById('page-title')?.focus()
    previousRoute.current = route
  }, [route])

  const showOnMap = (nextSelection) => {
    setSelection(nextSelection)
    window.location.hash = hrefFor('map')
  }

  let content
  if (index) {
    // Keep showing the last good data while a reload is in flight.
    content =
      route === 'map' ? (
        <NetworkMapPage index={index} selection={selection} onSelect={setSelection} />
      ) : (
        <DirectoryPage index={index} onShowOnMap={showOnMap} />
      )
  } else {
    content = (
      <div className="flex-1">
        <PageHeader title={TITLES[route]} />
        {network.status === 'error' ? (
          <StatusMessage tone="error" title="Couldn’t load the delivery network" onRetry={network.retry}>
            {network.error?.message}
          </StatusMessage>
        ) : (
          <StatusMessage tone="loading" title="Loading network…">
            Fetching locations and roads from the Flask API.
          </StatusMessage>
        )}
      </div>
    )
  }

  return (
    <AppShell
      route={route}
      status={network.status}
      counts={index && { locations: index.locations.length, roads: index.roads.length }}
      onReload={network.retry}
    >
      {content}
    </AppShell>
  )
}
