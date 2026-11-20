// Pure helpers that turn the API records into what the screens draw.
// No React here, so each function can be explained (and tested) on its own.

export const KIND_META = {
  DEPOT: { label: 'Depot', plural: 'Depots', order: 0, radius: 8 },
  HUB: { label: 'Hub', plural: 'Hubs', order: 1, radius: 9 },
  CUSTOMER: { label: 'Customer', plural: 'Customers', order: 2, radius: 6 },
}

export const kindMeta = (kind) =>
  KIND_META[kind] ?? { label: kind || 'Unknown', plural: kind || 'Unknown', order: 9, radius: 6 }

export function formatKm(value) {
  return `${Number(value).toLocaleString(undefined, { minimumFractionDigits: 1, maximumFractionDigits: 1 })} km`
}

export const plural = (count, word) => `${count} ${word}${count === 1 ? '' : 's'}`

/** "20 locations · 36 roads" */
export const countsLabel = (locations, roads) => `${plural(locations, 'location')} · ${plural(roads, 'road')}`

export function formatCoord(value) {
  return Number(value).toLocaleString(undefined, { maximumFractionDigits: 1 })
}

const pairKey = (a, b) => (a < b ? `${a}-${b}` : `${b}-${a}`)

/**
 * Builds lookups used by both screens:
 * - byId: location id -> location
 * - roadsByLocation: location id -> roads touching it
 * - isolated: ids of locations without any road
 * - pairCounts: how many roads join each unordered pair (to offset opposite one-ways)
 * - unknownRoads: roads whose endpoints are missing from the locations list
 */
export function buildIndex(locations, roads) {
  const byId = new Map(locations.map((location) => [location.id, location]))
  const roadsByLocation = new Map(locations.map((location) => [location.id, []]))
  const pairCounts = new Map()
  const unknownRoads = []

  for (const road of roads) {
    if (!byId.has(road.from_id) || !byId.has(road.to_id)) {
      unknownRoads.push(road)
      continue
    }
    roadsByLocation.get(road.from_id).push(road)
    roadsByLocation.get(road.to_id).push(road)
    const key = pairKey(road.from_id, road.to_id)
    pairCounts.set(key, (pairCounts.get(key) ?? 0) + 1)
  }

  const isolated = new Set(
    locations.filter((location) => roadsByLocation.get(location.id).length === 0).map((l) => l.id),
  )

  return { locations, roads, byId, roadsByLocation, pairCounts, isolated, unknownRoads }
}

export function locationName(index, id) {
  return index.byId.get(id)?.name ?? `Unknown location #${id}`
}

export function locationCode(index, id) {
  return index.byId.get(id)?.code ?? `#${id}`
}

export function sortLocations(locations) {
  return [...locations].sort(
    (a, b) => kindMeta(a.kind).order - kindMeta(b.kind).order || a.code.localeCompare(b.code),
  )
}

/** Locations that share exact x/y with another one (for an inspector note). */
export function coincidentCount(index, location) {
  return index.locations.filter((l) => l.id !== location.id && l.x === location.x && l.y === location.y)
    .length
}

/**
 * Fits the locations' x/y bounds into a width x height pixel box (uniform scale,
 * centred). Locations sharing exact coordinates are fanned out in a small ring so
 * each stays visible and clickable. Returns { points: Map(id -> {x, y}), scale }.
 *
 * Degenerate cases are explicit so the SVG never receives NaN:
 * a single location, or all locations on one point, are drawn at the centre.
 */
export function layoutLocations(locations, width, height, padding = Math.min(56, Math.max(28, width * 0.07))) {
  const points = new Map()
  const plotted = locations.filter((l) => Number.isFinite(l.x) && Number.isFinite(l.y))
  if (!plotted.length || width <= 0 || height <= 0) return { points, scale: 0 }

  const xs = plotted.map((l) => l.x)
  const ys = plotted.map((l) => l.y)
  const minX = Math.min(...xs)
  const maxX = Math.max(...xs)
  const minY = Math.min(...ys)
  const maxY = Math.max(...ys)
  const spanX = maxX - minX
  const spanY = maxY - minY

  const pad = Math.min(padding, width / 4, height / 4)
  const innerW = Math.max(width - pad * 2, 1)
  const innerH = Math.max(height - pad * 2, 1)
  const candidates = [spanX > 0 ? innerW / spanX : Infinity, spanY > 0 ? innerH / spanY : Infinity]
  const fit = Math.min(...candidates)
  const scale = Number.isFinite(fit) ? fit : 0 // 0 => everything on one point

  const centreX = (minX + maxX) / 2
  const centreY = (minY + maxY) / 2

  // Group by exact coordinates so stacked locations can be fanned out.
  const groups = new Map()
  for (const location of plotted) {
    const key = `${location.x},${location.y}`
    if (!groups.has(key)) groups.set(key, [])
    groups.get(key).push(location)
  }

  for (const group of groups.values()) {
    const { x, y } = group[0]
    const baseX = width / 2 + (x - centreX) * scale
    const baseY = height / 2 + (y - centreY) * scale
    const ring = group.length > 1 ? Math.max(14, group.length * 5) : 0
    group.forEach((location, i) => {
      const angle = (2 * Math.PI * i) / group.length - Math.PI / 2
      points.set(location.id, {
        x: baseX + ring * Math.cos(angle),
        y: baseY + ring * Math.sin(angle),
      })
    })
  }

  return { points, scale }
}

/**
 * Screen geometry for one road between projected points a and b.
 * - Endpoints are trimmed by the node radii so arrowheads sit at the node edge.
 * - If several roads join the same pair, each is shifted to the right of its own
 *   travel direction, so opposite one-way roads appear as two parallel lanes.
 * Returns null when the endpoints coincide (nothing meaningful to draw).
 */
export function roadGeometry(road, a, b, { pairCount = 1, fromRadius = 6, toRadius = 6 } = {}) {
  const dx = b.x - a.x
  const dy = b.y - a.y
  const length = Math.hypot(dx, dy)
  if (!(length > 1)) return null

  const ux = dx / length
  const uy = dy / length
  // Right-hand normal of the travel direction (SVG y axis points down).
  const nx = -uy
  const ny = ux
  const offset = pairCount > 1 ? 5 : 0

  const canTrim = length > fromRadius + toRadius + 4
  const startTrim = canTrim ? fromRadius + 2 : 0
  const endTrim = canTrim ? toRadius + 3 : 0

  const x1 = a.x + ux * startTrim + nx * offset
  const y1 = a.y + uy * startTrim + ny * offset
  const x2 = b.x - ux * endTrim + nx * offset
  const y2 = b.y - uy * endTrim + ny * offset
  const mid = { x: (a.x + b.x) / 2 + nx * offset, y: (a.y + b.y) / 2 + ny * offset }

  return {
    x1,
    y1,
    x2,
    y2,
    mid,
    normal: { x: nx, y: ny },
    angle: (Math.atan2(dy, dx) * 180) / Math.PI,
    length,
  }
}

// Candidate label positions around a node, in order of preference.
// dx/dy give the direction; anchor is the SVG text-anchor.
const LABEL_SIDES = [
  { side: 'right', dx: 1, dy: 0, anchor: 'start' },
  { side: 'left', dx: -1, dy: 0, anchor: 'end' },
  { side: 'below', dx: 0, dy: 1, anchor: 'middle' },
  { side: 'above', dx: 0, dy: -1, anchor: 'middle' },
  { side: 'below-right', dx: 0.7, dy: 0.7, anchor: 'start' },
  { side: 'above-right', dx: 0.7, dy: -0.7, anchor: 'start' },
  { side: 'below-left', dx: -0.7, dy: 0.7, anchor: 'end' },
  { side: 'above-left', dx: -0.7, dy: -0.7, anchor: 'end' },
].map((s) => ({ ...s, angle: Math.atan2(s.dy, s.dx) }))

/** Where the text of a label goes for a side, `gap` px from the node centre. */
export function labelPosition(side, gap) {
  const s = LABEL_SIDES.find((candidate) => candidate.side === side) ?? LABEL_SIDES[0]
  const vertical = s.dx === 0 ? 4 : 0 // centred labels need a little extra room
  return { x: s.dx * gap, y: s.dy * (gap + vertical), anchor: s.anchor }
}

/**
 * Picks the side of a node for its name label: the direction farthest (by angle)
 * from the roads leaving that node, so labels avoid sitting on top of roads.
 * Sides that would push a long label off the canvas edge are skipped.
 */
export function labelSide(point, neighbours, width, labelWidth = 130) {
  const allowed = LABEL_SIDES.filter(({ anchor }) => {
    if (anchor === 'start') return point.x + labelWidth < width
    if (anchor === 'end') return point.x - labelWidth > 0
    return point.x - labelWidth / 2 > 0 && point.x + labelWidth / 2 < width
  })
  if (!allowed.length) return 'below'
  if (!neighbours.length) return allowed[0].side

  const angles = neighbours.map((n) => Math.atan2(n.y - point.y, n.x - point.x))
  const gap = (a, b) => {
    const d = Math.abs(a - b) % (2 * Math.PI)
    return d > Math.PI ? 2 * Math.PI - d : d
  }
  let best = allowed[0]
  let bestScore = -1
  for (const candidate of allowed) {
    const score = Math.min(...angles.map((a) => gap(a, candidate.angle)))
    // Prefer earlier sides (right, left) unless another is clearly better.
    if (score > bestScore + 0.25) {
      best = candidate
      bestScore = score
    }
  }
  return best.side
}

/** Approximate text box for an SVG label (good enough for overlap tests). */
export function textBox({ x, y, anchor }, text, charWidth, height = 13) {
  const width = text.length * charWidth + 4
  const left = anchor === 'start' ? x : anchor === 'end' ? x - width : x - width / 2
  return { left, right: left + width, top: y - height / 2, bottom: y + height / 2 }
}

const overlaps = (a, b) => a.left < b.right && b.left < a.right && a.top < b.bottom && b.top < a.bottom

/**
 * Greedy label placement. Each candidate offers boxes in order of preference;
 * the first box that overlaps neither an obstacle nor an already placed label
 * wins. Candidates with no clear box are dropped, except `forced` ids, which
 * fall back to their first box. Returns Map(id -> index of the chosen box).
 */
export function placeLabels(candidates, obstacles, forced = new Set()) {
  const placed = []
  const chosen = new Map()
  const ordered = [...candidates].sort((a, b) => forced.has(b.id) - forced.has(a.id))
  for (const { id, boxes } of ordered) {
    const clear = (box) => !obstacles.some((o) => overlaps(o, box)) && !placed.some((p) => overlaps(p, box))
    let pick = boxes.findIndex(clear)
    if (pick === -1 && forced.has(id)) pick = 0
    if (pick !== -1) {
      placed.push(boxes[pick])
      chosen.set(id, pick)
    }
  }
  return chosen
}

export function pairCountFor(index, road) {
  return index.pairCounts.get(pairKey(road.from_id, road.to_id)) ?? 1
}

/** Text used by tooltips and screen readers for a road. */
export function describeRoad(index, road) {
  const from = locationName(index, road.from_id)
  const to = locationName(index, road.to_id)
  const direction = road.is_one_way ? `one-way from ${from} to ${to}` : `two-way between ${from} and ${to}`
  return `${formatKm(road.distance_km)}, ${direction}, ${road.is_closed ? 'closed' : 'open'}`
}

export function networkSummary(index) {
  const byKind = {}
  for (const location of index.locations) byKind[location.kind] = (byKind[location.kind] ?? 0) + 1
  return {
    byKind,
    roads: index.roads.length,
    oneWay: index.roads.filter((r) => r.is_one_way).length,
    closed: index.roads.filter((r) => r.is_closed).length,
    isolated: index.locations.filter((l) => index.isolated.has(l.id)),
  }
}
