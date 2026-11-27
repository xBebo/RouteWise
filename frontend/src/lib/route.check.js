// Self-check for lib/route.js. Run: node src/lib/route.check.js
import assert from 'node:assert/strict'
import { formatEta, humanizeWarning, pathNames, routeHeadline, routeMarkers } from './route.js'

const leg = (seq, from, to, stop = false) => ({ seq, from_id: from, to_id: to, from_name: `N${from}`, to_name: `N${to}`, is_delivery_stop: stop })

assert.equal(formatEta(0), '0 min')
assert.equal(formatEta(0.4), '< 1 min')
assert.equal(formatEta(10), '10 min')
assert.equal(formatEta(65.4), '1 h 05 min')

// Same-origin POINT: no legs, only a start marker.
const same = { mode: 'POINT', origin_id: 1, origin_name: 'N1', destination_id: 1, legs: [], ordered_stops: [] }
assert.deepEqual(routeMarkers(same), [{ id: 1, text: 'S', tone: 'start' }])
assert.deepEqual(pathNames(same), ['N1'])
assert.equal(routeHeadline(same), 'N1 (same origin)')

// RUN with pass-through node 3 and a return leg: stops numbered in visiting order only.
const run = {
  mode: 'RUN',
  origin_id: 1,
  origin_name: 'N1',
  destination_id: 1,
  ordered_stops: [2, 4],
  legs: [leg(1, 1, 2, true), leg(2, 2, 3), leg(3, 3, 4, true), leg(4, 4, 1)],
}
assert.deepEqual(
  routeMarkers(run).map((m) => m.text),
  ['S', '1', '2'],
)
assert.equal(routeHeadline(run), 'N1 · 2 stops')

const nameOf = (id) => `N${id}`
assert.equal(humanizeWarning('Unreachable stop(s) skipped: [20, 3].', nameOf), 'Unreachable stop(s) skipped: N20, N3.')
assert.equal(humanizeWarning('Return leg from stop 13 to depot 1 is unreachable.', nameOf), 'Return leg from stop N13 to depot N1 is unreachable.')
assert.equal(humanizeWarning('Something else 5.', nameOf), 'Something else 5.')

console.log('route.js self-check passed')
