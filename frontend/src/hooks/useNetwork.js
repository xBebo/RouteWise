import { useCallback, useEffect, useState } from 'react'
import { getNetwork } from '../services/api.js'

/**
 * Loads locations and roads once and exposes { status, data, error, retry }.
 * status: 'loading' | 'ready' | 'error'. Retry re-runs the request.
 */
export function useNetwork() {
  const [attempt, setAttempt] = useState(0)
  const [state, setState] = useState({ status: 'loading', data: null, error: null })

  useEffect(() => {
    const controller = new AbortController()
    getNetwork(controller.signal)
      .then((data) => setState({ status: 'ready', data, error: null }))
      .catch((error) => {
        if (!controller.signal.aborted) setState({ status: 'error', data: null, error })
      })
    return () => controller.abort()
  }, [attempt])

  const retry = useCallback(() => {
    setState((current) => ({ ...current, status: 'loading', error: null }))
    setAttempt((n) => n + 1)
  }, [])

  return { ...state, retry }
}
