import { useId, useMemo } from 'react'
import { useElementSize } from '../../hooks/useElementSize.js'
import {
  describeRoad,
  formatKm,
  kindMeta,
  labelPosition,
  labelSide,
  layoutLocations,
  pairCountFor,
  placeLabels,
  roadGeometry,
  textBox,
} from '../../lib/network.js'
import { NodeGlyph } from '../NodeGlyph.jsx'
import { routeMarkers, routeSummaryText } from '../../lib/route.js'

const LABEL_ROOM = 640 // px of map width needed before every customer name is shown

/**
 * Depot and hub names always show. Customer names show when the map is wide,
 * otherwise only for the selected location or the selected road's endpoints.
 */
const isLabelVisible = (location, roomy, focus) =>
  location.kind !== 'CUSTOMER' || roomy || Boolean(focus?.named.has(location.id))

/**
 * What the current selection emphasises (null = nothing selected):
 * nodes/roads stay at full opacity, `named` locations always get their name.
 */
function focusFor(index, selection) {
  if (!selection) return null
  if (selection.type === 'location') {
    const roads = index.roadsByLocation.get(selection.id) ?? []
    const nodes = new Set([selection.id])
    roads.forEach((road) => nodes.add(road.from_id).add(road.to_id))
    return { nodes, roads: new Set(roads.map((road) => road.id)), named: new Set([selection.id]) }
  }
  const road = index.roads.find((r) => r.id === selection.id)
  if (!road) return null
  const endpoints = new Set([road.from_id, road.to_id])
  return { nodes: endpoints, roads: new Set([road.id]), named: endpoints }
}

const DISTANCE_CHAR = 6.1 // px per character of the 10px monospace distance text
const LABEL_STOPS = [0.5, 0.35, 0.65] // where along a road its distance may go, in order of preference

const MARKER_TONES = {
  start: 'fill-slate-900',
  end: 'fill-accent-700',
  stop: 'fill-accent-600',
}

/**
 * SVG schematic of the network. Location x/y are projected into the measured
 * box (viewBox = pixel size), so glyphs and text keep a constant on-screen size.
 * Draw order: roads, route overlay, nodes, markers, so roads never cover a location.
 *
 * `route` (an API route result) draws its legs from location to location, so a
 * saved route still shows even if a road was later closed, edited or deleted.
 * Without `onSelect` the map is read-only: locations are not focusable buttons.
 */
export function NetworkMap({ index, selection = null, onSelect, showDistances = false, route = null }) {
  const [ref, { width, height }] = useElementSize()
  const markerId = useId().replace(/:/g, '')
  const interactive = Boolean(onSelect)
  const routeIds = route && new Set(route.path)
  const focus = routeIds ? { nodes: routeIds, roads: new Set(), named: routeIds } : focusFor(index, selection)
  const roadDim = route ? 0.4 : 0.18 // keep the network readable under a route
  const nodeDim = route ? 0.5 : 0.3
  const roomy = width >= LABEL_ROOM

  // 1. Project locations to pixels.
  const { points } = useMemo(() => layoutLocations(index.locations, width, height), [index, width, height])

  // 2. Road geometry (trimmed to node edges, opposite one-ways offset into lanes).
  const roads = useMemo(
    () =>
      index.roads
        .map((road) => {
          const a = points.get(road.from_id)
          const b = points.get(road.to_id)
          if (!a || !b) return null
          const pairCount = pairCountFor(index, road)
          const geometry = roadGeometry(road, a, b, {
            pairCount,
            fromRadius: kindMeta(index.byId.get(road.from_id).kind).radius,
            toRadius: kindMeta(index.byId.get(road.to_id).kind).radius,
          })
          if (!geometry) return null
          const text = formatKm(road.distance_km)
          // Paired lanes: push the pill just clear of its own lane (to the right of travel),
          // using the pill's extent along the normal so near-vertical roads work too.
          const { normal } = geometry
          const shift = pairCount > 1
            ? Math.abs(normal.x) * ((text.length * DISTANCE_CHAR + 6) / 2) + Math.abs(normal.y) * 6.5 + 3
            : 0
          const along = (t) => ({
            x: geometry.x1 + (geometry.x2 - geometry.x1) * t,
            y: geometry.y1 + (geometry.y2 - geometry.y1) * t,
          })
          // Candidate label spots along the road: middle first, then either side of it.
          const labels = LABEL_STOPS.map((t) => {
            const p = along(t)
            return { x: p.x + normal.x * shift, y: p.y + normal.y * shift, anchor: 'middle' }
          })
          // Closure badge sits near the start, away from the label spots.
          const badge = along(0.2)
          return { road, geometry, labels, badge, text }
        })
        .filter(Boolean),
    [index, points],
  )

  // 3. Node labels: pick the side with the fewest roads.
  const nodeLabels = useMemo(() => {
    const labels = new Map()
    for (const [id, point] of points) {
      const location = index.byId.get(id)
      const neighbours = index.roadsByLocation
        .get(id)
        .map((road) => points.get(road.from_id === id ? road.to_id : road.from_id))
        .filter(Boolean)
      const side = labelSide(point, neighbours, width)
      const position = labelPosition(side, kindMeta(location.kind).radius + 7)
      labels.set(id, position)
    }
    return labels
  }, [index, points, width])

  // 4. Distance labels. Candidates are every road (toggle on) or just the roads of
  //    the selection (toggle off). Roads of the selection are placed first; any
  //    label that would hit a node, a name or another distance is dropped.
  //    The selected road's own distance is always shown.
  const visibleDistances = useMemo(() => {
    const focus = focusFor(index, selection)
    const forced = new Set(selection?.type === 'road' ? [selection.id] : [])
    const inFocus = (road) => Boolean(focus?.roads.has(road.id))

    const obstacles = []
    for (const location of index.locations) {
      const point = points.get(location.id)
      if (!point) continue
      const r = kindMeta(location.kind).radius + 2
      obstacles.push({ left: point.x - r, right: point.x + r, top: point.y - r, bottom: point.y + r })
      if (isLabelVisible(location, roomy, focus)) {
        const label = nodeLabels.get(location.id)
        const charWidth = location.kind === 'CUSTOMER' ? 5.8 : 6.8
        obstacles.push(textBox({ ...label, x: point.x + label.x, y: point.y + label.y }, location.name, charWidth))
      }
    }
    for (const { road, badge } of roads) {
      if (road.is_closed) obstacles.push({ left: badge.x - 8, right: badge.x + 8, top: badge.y - 8, bottom: badge.y + 8 })
    }
    const candidates = roads
      .filter(({ road }) => showDistances || inFocus(road))
      .sort((a, b) => inFocus(b.road) - inFocus(a.road) || b.geometry.length - a.geometry.length)
      .map(({ road, labels, text }) => ({
        id: road.id,
        boxes: labels.map((label) => textBox(label, text, DISTANCE_CHAR, 13)),
      }))
    return placeLabels(candidates, obstacles, forced)
  }, [roads, nodeLabels, points, index, showDistances, roomy, selection])

  return (
    <div ref={ref} className="absolute inset-0">
      {width > 0 && height > 0 && (
        <svg
          width={width}
          height={height}
          viewBox={`0 0 ${width} ${height}`}
          role="group"
          aria-label={
            route
              ? `Route map. ${routeSummaryText(route)}`
              : `Network map with ${index.locations.length} locations and ${index.roads.length} roads. Locations are focusable; roads are listed in the details panel.`
          }
          className="block touch-manipulation select-none"
        >
          <defs>
            <marker
              id={`${markerId}-arrow`}
              viewBox="0 0 10 10"
              refX="8.5"
              refY="5"
              markerWidth="9"
              markerHeight="9"
              markerUnits="userSpaceOnUse"
              orient="auto"
            >
              <path d="M0 0.5L9 5L0 9.5z" className="fill-accent-600" />
            </marker>
          </defs>

          {/* Empty canvas: click/tap clears the selection. */}
          <rect width={width} height={height} fill="transparent" onClick={() => onSelect?.(null)} />

          {/* Roads (pointer targets; keyboard users reach roads via the details panel). */}
          <g aria-hidden="true">
            {roads.map(({ road, geometry: g, badge }) => {
              const active = focus?.roads.has(road.id)
              const selected = selection?.type === 'road' && selection.id === road.id
              const dim = focus && !active
              const stroke = road.is_closed
                ? 'stroke-closed'
                : active
                  ? 'stroke-accent-600'
                  : road.is_one_way
                    ? 'stroke-slate-500'
                    : 'stroke-slate-400'
              const chevron = { x: g.x1 + (g.x2 - g.x1) * 0.68, y: g.y1 + (g.y2 - g.y1) * 0.68 }
              return (
                <g
                  key={road.id}
                  data-road-id={road.id}
                  data-one-way={road.is_one_way || undefined}
                  data-closed={road.is_closed || undefined}
                  className={interactive ? 'group/road cursor-pointer' : 'group/road'}
                  opacity={dim ? roadDim : 1}
                  onClick={(event) => {
                    event.stopPropagation()
                    onSelect?.({ type: 'road', id: road.id })
                  }}
                >
                  <title>{describeRoad(index, road)}</title>
                  <line x1={g.x1} y1={g.y1} x2={g.x2} y2={g.y2} stroke="transparent" strokeWidth={16} />
                  <line
                    x1={g.x1}
                    y1={g.y1}
                    x2={g.x2}
                    y2={g.y2}
                    className={`${stroke} ${road.is_closed || !interactive ? '' : 'group-hover/road:stroke-slate-800'}`}
                    strokeWidth={selected ? 3.5 : active ? 2.75 : 1.75}
                    strokeDasharray={road.is_closed ? '6 4' : undefined}
                    strokeLinecap="round"
                    markerEnd={road.is_one_way ? `url(#${markerId}-arrow)` : undefined}
                    data-role="road-line"
                  />
                  {road.is_one_way && g.length > 60 && (
                    <path
                      d="M-3.5 -4L1.5 0L-3.5 4"
                      transform={`translate(${chevron.x} ${chevron.y}) rotate(${g.angle})`}
                      fill="none"
                      className="stroke-accent-600"
                      strokeWidth={2}
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    />
                  )}
                  {road.is_closed && (
                    <g transform={`translate(${badge.x} ${badge.y})`} data-role="closure">
                      <circle r={7} className="fill-white stroke-closed" strokeWidth={1.5} />
                      <path d="M-3 -3L3 3M3 -3L-3 3" className="stroke-closed" strokeWidth={1.8} strokeLinecap="round" />
                    </g>
                  )}
                </g>
              )
            })}
          </g>

          {/* Route overlay: cased, heavier stroke with direction chevrons; start/end halos. */}
          {route && (
            <g aria-hidden="true" data-role="route" className="pointer-events-none">
              {routeMarkers(route)
                .filter((marker) => marker.tone !== 'stop')
                .map((marker) => {
                  const p = points.get(marker.id)
                  const location = index.byId.get(marker.id)
                  if (!p || !location) return null
                  return (
                    <circle
                      key={`halo-${marker.id}`}
                      cx={p.x}
                      cy={p.y}
                      r={kindMeta(location.kind).radius + 7}
                      className="fill-accent-100 stroke-accent-600"
                      strokeWidth={2}
                    />
                  )
                })}
              {route.legs.map((leg) => {
                const a = points.get(leg.from_id)
                const b = points.get(leg.to_id)
                if (!a || !b) return null
                const length = Math.hypot(b.x - a.x, b.y - a.y)
                const angle = (Math.atan2(b.y - a.y, b.x - a.x) * 180) / Math.PI
                return (
                  <g key={leg.seq} data-route-leg={leg.seq}>
                    <line x1={a.x} y1={a.y} x2={b.x} y2={b.y} className="stroke-white" strokeWidth={9} strokeLinecap="round" />
                    <line x1={a.x} y1={a.y} x2={b.x} y2={b.y} className="stroke-accent-600" strokeWidth={5} strokeLinecap="round" />
                    {length > 44 && (
                      <path
                        d="M-2.5 -3L1.5 0L-2.5 3"
                        transform={`translate(${(a.x + b.x) / 2} ${(a.y + b.y) / 2}) rotate(${angle})`}
                        fill="none"
                        className="stroke-white"
                        strokeWidth={1.8}
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      />
                    )}
                  </g>
                )
              })}
            </g>
          )}

          {/* Locations */}
          <g>
            {index.locations.map((location) => {
              const point = points.get(location.id)
              if (!point) return null
              const meta = kindMeta(location.kind)
              const selected = selection?.type === 'location' && selection.id === location.id
              const dim = focus && !focus.nodes.has(location.id)
              const isolated = index.isolated.has(location.id)
              const roadCount = index.roadsByLocation.get(location.id).length
              const label = nodeLabels.get(location.id)
              const select = () => onSelect?.({ type: 'location', id: location.id })
              return (
                <g
                  key={location.id}
                  transform={`translate(${point.x} ${point.y})`}
                  {...(interactive && {
                    role: 'button',
                    tabIndex: 0,
                    'aria-pressed': selected,
                    'aria-label': `${meta.label}: ${location.name} (${location.code}), ${
                      isolated ? 'isolated, no roads' : `${roadCount} ${roadCount === 1 ? 'road' : 'roads'}`
                    }`,
                    onKeyDown: (event) => {
                      if (event.key === 'Enter' || event.key === ' ') {
                        event.preventDefault()
                        select()
                      }
                    },
                  })}
                  data-location-id={location.id}
                  data-kind={location.kind}
                  className={`group outline-none ${interactive ? 'cursor-pointer' : ''}`}
                  opacity={dim ? nodeDim : 1}
                  onClick={(event) => {
                    event.stopPropagation()
                    select()
                  }}
                >
                  <title>{`${location.name} · ${location.code}`}</title>
                  <circle r={16} fill="transparent" />
                  {selected && <circle r={meta.radius + 7} className="fill-accent-100 stroke-accent-600" strokeWidth={1.5} />}
                  {isolated && (
                    <circle
                      r={meta.radius + 6}
                      fill="none"
                      className="stroke-slate-500"
                      strokeWidth={1.25}
                      strokeDasharray="3 3"
                      data-role="isolated"
                    />
                  )}
                  <circle
                    r={meta.radius + 10}
                    fill="none"
                    className="stroke-accent-600 opacity-0 group-focus-visible:opacity-100"
                    strokeWidth={2.5}
                  />
                  <NodeGlyph kind={location.kind} />
                  <text
                    x={label.x}
                    y={label.y}
                    textAnchor={label.anchor}
                    dominantBaseline="central"
                    className={`map-label pointer-events-none ${
                      location.kind === 'CUSTOMER' ? 'fill-slate-700 text-[11px]' : 'fill-slate-900 text-xs font-semibold'
                    } ${selected ? 'fill-accent-700 font-semibold' : ''} ${
                      isLabelVisible(location, roomy, focus) ? '' : 'opacity-0 group-hover:opacity-100 group-focus-visible:opacity-100'
                    }`}
                  >
                    {location.name}
                  </text>
                </g>
              )
            })}
          </g>
          {/* Distance labels: own top layer so nothing covers a placed label. */}
          <g aria-hidden="true" className="pointer-events-none">
            {roads.map(({ road, labels, text }) => {
              if (!visibleDistances.has(road.id)) return null
              const label = labels[visibleDistances.get(road.id)]
              const selected = selection?.type === 'road' && selection.id === road.id
              const dim = focus && !focus.roads.has(road.id)
              const pillWidth = text.length * DISTANCE_CHAR + 6
              return (
                <g key={road.id} data-role="distance" data-distance-for={road.id} opacity={dim ? 0.18 : 1}>
                  <rect
                    x={label.x - pillWidth / 2}
                    y={label.y - 6.5}
                    width={pillWidth}
                    height={13}
                    rx={3}
                    className={selected ? 'fill-accent-50 stroke-accent-600' : 'fill-white'}
                    strokeWidth={selected ? 1 : 0}
                  />
                  <text
                    x={label.x}
                    y={label.y}
                    textAnchor="middle"
                    dominantBaseline="central"
                    className={`font-mono text-[10px] tabular-nums ${
                      selected ? 'fill-accent-700 font-semibold' : road.is_closed ? 'fill-closed' : 'fill-slate-600'
                    }`}
                  >
                    {text}
                  </text>
                </g>
              )
            })}
          </g>

          {/* Route markers on top: S = start, E = end, 1..n = delivery stops in visiting order. */}
          {route && (
            <g aria-hidden="true" className="pointer-events-none" data-role="route-markers">
              {routeMarkers(route).map((marker) => {
                const p = points.get(marker.id)
                const location = index.byId.get(marker.id)
                if (!p || !location) return null
                const r = kindMeta(location.kind).radius
                return (
                  <g key={`${marker.tone}-${marker.id}`} transform={`translate(${p.x + r + 3} ${p.y - r - 3})`} data-marker={marker.text}>
                    <circle r={8.5} className={`${MARKER_TONES[marker.tone]} stroke-white`} strokeWidth={1.5} />
                    <text textAnchor="middle" dominantBaseline="central" className="fill-white text-[10px] font-semibold tabular-nums">
                      {marker.text}
                    </text>
                  </g>
                )
              })}
            </g>
          )}
        </svg>
      )}
    </div>
  )
}
