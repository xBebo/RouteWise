import { useEffect, useRef, useState } from 'react'
import { Button } from '../components/Button.jsx'
import { MapInspector } from '../components/map/MapInspector.jsx'
import { MapLegend } from '../components/map/MapLegend.jsx'
import { NetworkMap } from '../components/map/NetworkMap.jsx'
import { PageHeader } from '../components/PageHeader.jsx'
import { StatusMessage } from '../components/StatusMessage.jsx'
import { countsLabel, describeRoad, locationName } from '../lib/network.js'

function announce(index, selection) {
  if (selection?.type === 'location') {
    const location = index.byId.get(selection.id)
    if (location) return `Selected ${location.name}.`
  }
  if (selection?.type === 'road') {
    const road = index.roads.find((r) => r.id === selection.id)
    if (road) return `Selected road ${locationName(index, road.from_id)} to ${locationName(index, road.to_id)}: ${describeRoad(index, road)}.`
  }
  return ''
}

const wideScreen = () => window.matchMedia('(min-width: 1024px)').matches

export function NetworkMapPage({ index, selection, onSelect }) {
  // Distance labels are dense on small screens, so they start hidden there.
  const [showDistances, setShowDistances] = useState(wideScreen)
  const inspectorRef = useRef(null)
  const { locations, roads } = index

  // Esc clears the selection wherever focus is on this page.
  useEffect(() => {
    const onKeyDown = (event) => {
      if (event.key === 'Escape') onSelect(null)
    }
    document.addEventListener('keydown', onKeyDown)
    return () => document.removeEventListener('keydown', onKeyDown)
  }, [onSelect])

  // Selecting from the details panel replaces the focused button; keep focus in the panel.
  // Only on a selection change, never on first render (that would steal focus on page load).
  const previousSelection = useRef(selection)
  useEffect(() => {
    if (previousSelection.current !== selection && document.activeElement === document.body) {
      inspectorRef.current?.focus()
    }
    previousSelection.current = selection
  }, [selection])

  return (
    <div className="flex flex-1 flex-col lg:min-h-0">
      <PageHeader
        title="Network Map"
        meta={countsLabel(locations.length, roads.length)}
      >
        {locations.length > 0 && (
          <Button
            size="sm"
            aria-pressed={showDistances}
            onClick={() => setShowDistances((value) => !value)}
          >
            <span
              aria-hidden="true"
              className={`flex size-3.5 items-center justify-center rounded-[3px] border ${
                showDistances ? 'border-accent-600 bg-accent-600 text-white' : 'border-stone-400 bg-white'
              }`}
            >
              {showDistances && (
                <svg width="9" height="9" viewBox="0 0 10 10">
                  <path d="M1.5 5.5l2.3 2.2L8.5 2.5" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
                </svg>
              )}
            </span>
            Show distances
          </Button>
        )}
      </PageHeader>

      {locations.length === 0 ? (
        <StatusMessage tone="empty" title="No locations in the network yet">
          <p>
            Load the sample network with{' '}
            <code className="rounded bg-stone-200 px-1 py-0.5 font-mono text-xs">python -m scripts.seed_data --reset</code>{' '}
            or add locations through the API, then reload.
          </p>
        </StatusMessage>
      ) : (
        <div className="flex flex-1 flex-col lg:min-h-0 lg:flex-row">
          <section aria-labelledby="map-title" className="relative flex flex-col bg-stone-50 lg:min-w-0 lg:flex-1">
            <h2 id="map-title" className="sr-only">
              Network schematic
            </h2>
            <div className="relative aspect-[4/5] max-h-[70dvh] w-full sm:aspect-[4/3] lg:aspect-auto lg:max-h-none lg:flex-1">
              <NetworkMap index={index} selection={selection} onSelect={onSelect} showDistances={showDistances} />
              {roads.length === 0 && (
                <p role="status" className="absolute top-3 right-3 left-3 rounded-md border border-stone-200 bg-white px-3 py-2 text-sm text-slate-700 sm:right-auto">
                  No roads yet. Locations are shown without connections.
                </p>
              )}
            </div>
            <MapLegend className="border-t border-stone-200 bg-white px-4 py-3 lg:hidden" />
          </section>

          <aside
            ref={inspectorRef}
            tabIndex={-1}
            aria-label="Selection details"
            className="border-t focus:outline-none border-stone-200 bg-white p-4 sm:p-5 lg:w-80 lg:shrink-0 lg:overflow-y-auto lg:border-t-0 lg:border-l"
          >
            <MapInspector index={index} selection={selection} onSelect={onSelect} />
            <MapLegend className="mt-6 hidden border-t border-stone-200 pt-4 lg:block" />
          </aside>
        </div>
      )}

      <p className="sr-only" aria-live="polite">
        {announce(index, selection)}
      </p>
    </div>
  )
}
