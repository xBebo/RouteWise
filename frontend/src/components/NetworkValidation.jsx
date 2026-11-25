import { useState } from 'react'
import { requestNetwork } from '../services/api.js'

export function NetworkValidation({ index }) {
  const [chosenDepot, setChosenDepot] = useState('')
  const [state, setState] = useState(null)
  const [busy, setBusy] = useState(false)
  const depots = index.locations.filter((loc) => loc.kind === 'DEPOT')
  const depot = depots.find((loc) => String(loc.id) === chosenDepot) ?? depots[0]
  const current = state?.index === index && state.depot === depot?.id ? state : null
  const label = (id) => index.byId.get(id)?.name ?? id

  async function run(event) {
    event.preventDefault()
    if (!depot) return
    setBusy(true)
    setState(null)
    try {
      const data = await requestNetwork('network/validation?depot_id=' + depot.id)
      setState({ index, depot: depot.id, data })
    } catch (error) {
      setState({ index, depot: depot.id, error: error.message })
    } finally {
      setBusy(false)
    }
  }

  return (
    <section aria-label="Network validation" className="mb-3 rounded border border-slate-200 bg-white p-3">
      {depot ? (
        <form onSubmit={run} className="flex flex-wrap items-center gap-2">
          <label>Depot{' '}
            <select value={depot.id} onChange={(event) => setChosenDepot(event.target.value)} disabled={busy} className="rounded border p-1">
              {depots.map((loc) => <option key={loc.id} value={loc.id}>{loc.name}</option>)}
            </select>
          </label>
          <button type="submit" disabled={busy} className="rounded border px-2 py-1">{busy ? 'Validating…' : 'Validate network'}</button>
        </form>
      ) : <p>Add a depot to validate reachability.</p>}
      {current?.error && <p role="alert">{current.error}</p>}
      {current?.data && <div role="status" className="mt-2">
        <p>Reachable from depot: {current.data.reachable_count}</p>
        <p>Isolated: {current.data.isolated.map(label).join(', ') || 'None'}</p>
        <p>Unreachable: {current.data.unreachable.map(label).join(', ') || 'None'}</p>
      </div>}
    </section>
  )
}
