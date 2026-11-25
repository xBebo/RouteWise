import { useState } from 'react'
import { requestNetwork } from '../services/api.js'

const control = 'rounded border border-slate-400 bg-white px-2 py-1'
const empty = {
  locations: { code: '', name: '', kind: 'CUSTOMER', x: '', y: '' },
  roads: { from_id: '', to_id: '', distance_km: '', is_one_way: false, is_closed: false },
}

export function NetworkEditor({ index, onChanged }) {
  const [resource, setResource] = useState('locations')
  const [id, setId] = useState('')
  const [draft, setDraft] = useState(empty.locations)
  const [message, setMessage] = useState(null)
  const [busy, setBusy] = useState(false)

  const rows = index[resource]
  const roadLabel = (road) => [road.from_id, road.to_id].map((key) => index.byId.get(key)?.name ?? key).join(road.is_one_way ? ' → ' : ' ↔ ')

  function select(nextId, nextResource = resource) {
    const row = index[nextResource].find((item) => String(item.id) === nextId)
    setId(nextId)
    setDraft(row ? Object.fromEntries(Object.keys(empty[nextResource]).map((key) => [key, row[key]])) : empty[nextResource])
    setMessage(null)
  }

  function update(key, value) {
    setDraft((current) => ({ ...current, [key]: value }))
  }

  async function save(method) {
    if (method === 'DELETE' && !window.confirm('Delete this record?')) return
    setBusy(true)
    setMessage(null)
    const body = resource === 'locations'
      ? { ...draft, x: Number(draft.x), y: Number(draft.y) }
      : { ...draft, from_id: Number(draft.from_id), to_id: Number(draft.to_id), distance_km: Number(draft.distance_km) }
    try {
      await requestNetwork(id ? resource + '/' + id : resource, method, method === 'DELETE' ? undefined : body)
      select('')
      setMessage({ text: method === 'DELETE' ? 'Record deleted.' : 'Record saved.' })
      onChanged()
    } catch (error) {
      setMessage({ error: true, text: error.message })
    } finally {
      setBusy(false)
    }
  }

  const input = (key, label, options = {}) => (
    <label className="grid gap-1">{label}
      <input className={control} required value={draft[key]} onChange={(event) => update(key, event.target.value)} {...options} />
    </label>
  )

  const endpoint = (key, label) => (
    <label className="grid gap-1">{label}
      <select aria-label={label} className={control} required value={draft[key]} onChange={(event) => update(key, event.target.value)}>
        <option value="">Select a location</option>
        {index.locations.map((loc) => <option key={loc.id} value={loc.id}>{loc.code} · {loc.name}</option>)}
      </select>
    </label>
  )

  return (
    <details className="mb-4 rounded border border-slate-200 bg-white p-4">
      <summary className="cursor-pointer font-semibold">Manage locations and roads</summary>
      <form className="mt-3 grid gap-3" onSubmit={(event) => {
        event.preventDefault()
        void save(id ? 'PATCH' : 'POST')
      }}>
        <fieldset disabled={busy} className="grid gap-3 sm:grid-cols-2">
          <label className="grid gap-1">Record type
            <select aria-label="Record type" className={control} value={resource} onChange={(event) => {
              setResource(event.target.value)
              select('', event.target.value)
            }}>
              <option value="locations">Location</option>
              <option value="roads">Road</option>
            </select>
          </label>
          <label className="grid gap-1">Record
            <select aria-label="Record" className={control} value={id} onChange={(event) => select(event.target.value)}>
              <option value="">Add new</option>
              {rows.map((row) => <option key={row.id} value={row.id}>{resource === 'locations' ? row.code + ' · ' + row.name : roadLabel(row)}</option>)}
            </select>
          </label>
          {resource === 'locations' ? <>
            {input('code', 'Code')}{input('name', 'Name')}
            <label className="grid gap-1">Type
              <select className={control} value={draft.kind} onChange={(event) => update('kind', event.target.value)}>
                {['DEPOT', 'HUB', 'CUSTOMER'].map((kind) => <option key={kind}>{kind}</option>)}
              </select>
            </label>
            {input('x', 'X', { type: 'number', min: 0, max: 1000, step: 'any' })}
            {input('y', 'Y', { type: 'number', min: 0, max: 1000, step: 'any' })}
          </> : <>
            {endpoint('from_id', 'From')}{endpoint('to_id', 'To')}
            {input('distance_km', 'Distance (km)', { type: 'number', min: 0, max: 500, step: 'any' })}
            <div className="flex gap-4">
              <label><input type="checkbox" checked={draft.is_one_way ?? false} onChange={(event) => update('is_one_way', event.target.checked)} /> One-way</label>
              <label><input type="checkbox" checked={draft.is_closed ?? false} onChange={(event) => update('is_closed', event.target.checked)} /> Closed</label>
            </div>
          </>}
          <div className="flex gap-2">
            <button className={control} type="submit">{id ? 'Save changes' : 'Add record'}</button>
            {id && <button className={control} type="button" onClick={() => void save('DELETE')}>Delete</button>}
          </div>
        </fieldset>
        {message && <p role={message.error ? 'alert' : 'status'}>{message.text}</p>}
      </form>
    </details>
  )
}
