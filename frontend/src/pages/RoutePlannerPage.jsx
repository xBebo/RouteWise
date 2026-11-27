import { useEffect, useId, useRef, useState } from 'react'
import { Button } from '../components/Button.jsx'
import { PageHeader } from '../components/PageHeader.jsx'
import { StatusMessage } from '../components/StatusMessage.jsx'
import { RouteResult } from '../components/route/RouteResult.jsx'
import { RouteWorkspace } from '../components/route/RouteWorkspace.jsx'
import { hrefFor } from '../hooks/useHashRoute.js'
import { locationName, sortLocations } from '../lib/network.js'
import { MAX_STOPS, routeSummaryText } from '../lib/route.js'
import { planDeliveryRun, planPointRoute, saveRoute } from '../services/api.js'

const control =
  'h-9 w-full rounded-md border bg-white px-2.5 text-sm text-slate-900 aria-[invalid=true]:border-closed'
const labelText = 'text-xs font-medium text-slate-700'

function FieldError({ id, message }) {
  if (!message) return null
  return (
    <p id={id} className="text-xs text-closed">
      {message}
    </p>
  )
}

/** Labelled <select> of locations with field-level error wiring. */
function LocationSelect({ label, value, onChange, locations, error, placeholder }) {
  const id = useId()
  return (
    <div className="grid gap-1">
      <label htmlFor={id} className={labelText}>
        {label}
      </label>
      <select
        id={id}
        className={`${control} border-stone-300`}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        aria-invalid={Boolean(error)}
        aria-describedby={error ? `${id}-error` : undefined}
      >
        <option value="">{placeholder}</option>
        {locations.map((location) => (
          <option key={location.id} value={location.id}>
            {location.name} ({location.code})
          </option>
        ))}
      </select>
      <FieldError id={`${id}-error`} message={error} />
    </div>
  )
}

function validate(mode, form) {
  const errors = {}
  if (mode === 'POINT') {
    if (!form.originId) errors.origin_id = 'Choose an origin.'
    if (!form.destinationId) errors.destination_id = 'Choose a destination.'
  } else {
    if (!form.depotId) errors.depot_id = 'Choose a depot.'
    if (form.stopIds.length < 1 || form.stopIds.length > MAX_STOPS) errors.stop_ids = `Choose 1–${MAX_STOPS} stops.`
  }
  const speed = Number(form.speed)
  if (form.speed.trim() === '' || !Number.isFinite(speed) || speed <= 0) {
    errors.avg_speed_kmh = 'Enter an average speed greater than 0 km/h.'
  }
  return errors
}

function requestFor(mode, form) {
  const avg_speed_kmh = Number(form.speed)
  return mode === 'POINT'
    ? { origin_id: Number(form.originId), destination_id: Number(form.destinationId), avg_speed_kmh }
    : { depot_id: Number(form.depotId), stop_ids: form.stopIds, avg_speed_kmh, return_to_depot: form.returnToDepot }
}

/** Error / no-route feedback for a failed plan request. */
function PlanError({ error, mode, index }) {
  if (error.status === 422) {
    const skipped = error.body?.unreachable_stops ?? []
    return (
      <StatusMessage tone="error" title={mode === 'POINT' ? 'No route found' : 'No stop is reachable'} compact>
        <p>{error.message}</p>
        {skipped.length > 0 && <p className="mt-1">Unreachable: {skipped.map((id) => locationName(index, id)).join(', ')}.</p>}
        <p className="mt-1">Closed roads and one-way restrictions can cut a location off. Check the Network Map.</p>
      </StatusMessage>
    )
  }
  if (error.status === 400) {
    return (
      <StatusMessage tone="error" title="Check the highlighted fields" compact>
        {error.message}
      </StatusMessage>
    )
  }
  return (
    <StatusMessage tone="error" title="Couldn’t plan the route" compact>
      {error.message}
    </StatusMessage>
  )
}

export function RoutePlannerPage({ index }) {
  const [mode, setMode] = useState('POINT')
  const [form, setForm] = useState({
    originId: '',
    destinationId: '',
    depotId: '',
    stopIds: [],
    returnToDepot: false,
    speed: '40',
  })
  const [submitted, setSubmitted] = useState(false) // show client validation only after a first attempt
  // Each plan is one attempt. Any input/mode change starts a new attempt and drops the preview;
  // late plan or save responses for an older attempt are ignored.
  const [preview, setPreview] = useState(null) // { attempt, index, mode, request, status: 'loading'|'ready'|'error', route?, error? }
  const [save, setSave] = useState(null) // { attempt, status: 'saving'|'saved'|'error', route?, error? }
  const attempt = useRef(0)
  const planController = useRef(null)
  const savingAttempt = useRef(null) // guards double-clicks on Save within one attempt
  const stopsId = useId()
  const speedId = useId()

  useEffect(() => () => planController.current?.abort(), [])

  const locations = sortLocations(index.locations)
  const depots = locations.filter((location) => location.kind === 'DEPOT')
  const stopCandidates = locations.filter((location) => String(location.id) !== form.depotId)
  const current = preview?.index === index ? preview : null // a network reload also hides it
  const currentSave = current && save?.attempt === current.attempt ? save : null
  const route = current?.status === 'ready' ? current.route : null

  const clientErrors = submitted ? validate(mode, form) : {}
  const serverErrors = current?.status === 'error' ? (current.error.body?.fields ?? {}) : {}
  const errors = { ...serverErrors, ...clientErrors }

  function invalidate() {
    attempt.current += 1
    planController.current?.abort()
    setPreview(null)
    setSave(null)
  }
  const changeMode = (value) => {
    if (value === mode) return
    invalidate()
    setMode(value)
  }
  const update = (patch) => {
    invalidate()
    setForm((value) => ({ ...value, ...patch }))
  }
  const toggleStop = (id) =>
    update({
      stopIds: form.stopIds.includes(id)
        ? form.stopIds.filter((stop) => stop !== id)
        : stopCandidates.map((l) => l.id).filter((stop) => stop === id || form.stopIds.includes(stop)),
    })

  async function plan(event) {
    event.preventDefault()
    setSubmitted(true)
    if (Object.keys(validate(mode, form)).length) return

    // A fresh attempt, even with identical inputs: starts unsaved, and older responses can't land.
    const id = ++attempt.current
    planController.current?.abort()
    const controller = new AbortController()
    planController.current = controller
    const base = { attempt: id, index, mode, request: requestFor(mode, form) }
    setSave(null)
    setPreview({ ...base, status: 'loading' })
    try {
      const result = await (mode === 'POINT' ? planPointRoute : planDeliveryRun)(base.request, controller.signal)
      if (attempt.current === id) setPreview({ ...base, status: 'ready', route: result })
    } catch (error) {
      if (attempt.current === id && !controller.signal.aborted) setPreview({ ...base, status: 'error', error })
    }
  }

  async function saveCurrent() {
    if (!route || savingAttempt.current === current.attempt) return
    const id = current.attempt
    savingAttempt.current = id
    setSave({ attempt: id, status: 'saving' })
    try {
      // The API recomputes before saving; its result replaces the preview as the source of truth.
      // A save may still complete on the server after a newer attempt starts; it just won't update the UI.
      const saved = await saveRoute({ mode: current.mode, ...current.request })
      if (attempt.current !== id) return
      setPreview((value) => (value?.attempt === id ? { ...value, route: saved } : value))
      setSave({ attempt: id, status: 'saved', route: saved })
    } catch (error) {
      if (attempt.current === id) setSave({ attempt: id, status: 'error', error })
    } finally {
      if (savingAttempt.current === id) savingAttempt.current = null
    }
  }

  const describedSpeed = errors.avg_speed_kmh ? `${speedId}-error` : undefined

  const controls = (
    <form onSubmit={plan} noValidate className="space-y-4 p-4 sm:p-5">
      <fieldset>
        <legend className={labelText}>Planning mode</legend>
        <div className="mt-1 grid grid-cols-2 gap-1 rounded-lg bg-stone-100 p-1">
          {[
            ['POINT', 'Point to point'],
            ['RUN', 'Multi-stop run'],
          ].map(([value, label]) => (
            <button
              key={value}
              type="button"
              aria-pressed={mode === value}
              onClick={() => changeMode(value)}
              className={`h-8 rounded-md text-sm font-medium ${
                mode === value ? 'bg-white text-accent-700 shadow-sm ring-1 ring-stone-200' : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              {label}
            </button>
          ))}
        </div>
      </fieldset>

      {mode === 'POINT' ? (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-1">
          <LocationSelect
            label="Origin"
            placeholder="Choose origin"
            value={form.originId}
            onChange={(originId) => update({ originId })}
            locations={locations}
            error={errors.origin_id}
          />
          <LocationSelect
            label="Destination"
            placeholder="Choose destination"
            value={form.destinationId}
            onChange={(destinationId) => update({ destinationId })}
            locations={locations}
            error={errors.destination_id}
          />
        </div>
      ) : depots.length === 0 ? (
        <p role="status" className="rounded-md border border-stone-200 bg-stone-50 px-3 py-2 text-sm text-slate-700">
          The network has no depot. Add a location of type Depot to plan a delivery run.
        </p>
      ) : (
        <>
          <LocationSelect
            label="Depot"
            placeholder="Choose depot"
            value={form.depotId}
            onChange={(depotId) => update({ depotId, stopIds: form.stopIds.filter((id) => String(id) !== depotId) })}
            locations={depots}
            error={errors.depot_id}
          />
          <fieldset aria-describedby={errors.stop_ids ? `${stopsId}-error` : undefined}>
            <legend className={`${labelText} flex w-full justify-between`}>
              <span>Delivery stops</span>
              <span className="font-normal text-slate-500 tabular-nums">
                {form.stopIds.length} of {MAX_STOPS} max
              </span>
            </legend>
            <ul
              className={`mt-1 max-h-56 divide-y divide-stone-100 overflow-y-auto rounded-md border bg-white ${
                errors.stop_ids ? 'border-closed' : 'border-stone-300'
              }`}
            >
              {stopCandidates.map((location) => {
                const checked = form.stopIds.includes(location.id)
                return (
                  <li key={location.id}>
                    <label className="flex cursor-pointer items-center gap-2.5 px-2.5 py-1.5 text-sm has-[:disabled]:cursor-not-allowed has-[:disabled]:text-slate-400">
                      <input
                        type="checkbox"
                        className="size-4 accent-accent-600"
                        checked={checked}
                        disabled={!checked && form.stopIds.length >= MAX_STOPS}
                        onChange={() => toggleStop(location.id)}
                      />
                      <span className="min-w-0 flex-1 truncate">{location.name}</span>
                      <span className="font-mono text-xs text-slate-500">{location.code}</span>
                    </label>
                  </li>
                )
              })}
            </ul>
            <FieldError id={`${stopsId}-error`} message={errors.stop_ids} />
          </fieldset>
          <label className="flex items-center gap-2.5 text-sm text-slate-800">
            <input
              type="checkbox"
              className="size-4 accent-accent-600"
              checked={form.returnToDepot}
              onChange={(event) => update({ returnToDepot: event.target.checked })}
            />
            Return to depot after the last stop
          </label>
        </>
      )}

      <div className="grid gap-1">
        <label htmlFor={speedId} className={labelText}>
          Average speed (km/h)
        </label>
        <input
          id={speedId}
          type="number"
          inputMode="decimal"
          min="0"
          step="any"
          className={`${control} border-stone-300 font-mono tabular-nums`}
          value={form.speed}
          onChange={(event) => update({ speed: event.target.value })}
          aria-invalid={Boolean(errors.avg_speed_kmh)}
          aria-describedby={describedSpeed}
        />
        <FieldError id={`${speedId}-error`} message={errors.avg_speed_kmh} />
      </div>

      <Button
        type="submit"
        variant="primary"
        className="w-full"
        disabled={current?.status === 'loading' || (mode === 'RUN' && depots.length === 0)}
      >
        {current?.status === 'loading' ? 'Planning…' : mode === 'POINT' ? 'Find shortest route' : 'Plan delivery run'}
      </Button>
    </form>
  )

  const saveActions = route && (
    <div className="flex flex-col items-end gap-1">
      {currentSave?.status === 'saved' ? (
        <a
          href={hrefFor(`history/${currentSave.route.id}`)}
          className="inline-flex h-8 items-center rounded-md px-2.5 text-xs font-medium text-accent-700 ring-1 ring-accent-600/40 ring-inset hover:bg-accent-50"
        >
          Saved · view in history
        </a>
      ) : (
        <Button size="sm" variant="primary" onClick={saveCurrent} disabled={currentSave?.status === 'saving'}>
          {currentSave?.status === 'saving' ? 'Saving…' : 'Save route'}
        </Button>
      )}
    </div>
  )

  let result
  if (current?.status === 'loading') {
    result = (
      <StatusMessage tone="loading" title="Planning route…" compact>
        The Flask API is calculating the route.
      </StatusMessage>
    )
  } else if (current?.status === 'error') {
    result = <PlanError error={current.error} mode={mode} index={index} />
  } else if (route) {
    result = (
      <>
        {currentSave?.status === 'error' && (
          <p role="alert" className="mx-4 mt-4 rounded-md border border-closed/30 bg-closed-50 px-3 py-2 text-sm text-closed sm:mx-5">
            Couldn’t save the route: {currentSave.error.message}
          </p>
        )}
        <RouteResult
          route={route}
          index={index}
          heading={route.id != null ? 'Saved route' : 'Route preview'}
          actions={saveActions}
        />
      </>
    )
  } else {
    result = (
      <p className="p-4 text-sm text-slate-600 sm:p-5">
        {mode === 'POINT'
          ? 'Choose an origin and destination, then find the shortest open route.'
          : 'Choose a depot and up to eight stops. The run order comes from a nearest-neighbour heuristic.'}
      </p>
    )
  }

  return (
    <div className="flex flex-1 flex-col lg:min-h-0">
      <PageHeader title="Route Planner" meta="Shortest paths and delivery runs on the current network" />
      {index.locations.length === 0 ? (
        <StatusMessage tone="empty" title="No locations in the network yet">
          Add locations and roads in Locations &amp; Roads, then plan a route.
        </StatusMessage>
      ) : (
        <RouteWorkspace index={index} route={route} controls={controls} result={result} />
      )}
      <p className="sr-only" aria-live="polite">
        {current?.status === 'ready' ? routeSummaryText(route) : current?.status === 'error' ? current.error.message : ''}
      </p>
    </div>
  )
}
