import { Button } from './Button.jsx'

const icons = {
  loading: (
    <svg width="28" height="28" viewBox="0 0 28 28" aria-hidden="true" className="motion-safe:animate-pulse">
      <path d="M6 20L14 8l8 12" fill="none" className="stroke-stone-300" strokeWidth="1.5" />
      <rect x="3" y="17" width="6" height="6" rx="1" className="fill-slate-400" />
      <path d="M14 4.5l3.5 3.5-3.5 3.5-3.5-3.5z" className="fill-slate-400" />
      <circle cx="22" cy="20" r="3" className="fill-white stroke-slate-400" strokeWidth="1.5" />
    </svg>
  ),
  empty: (
    <svg width="28" height="28" viewBox="0 0 28 28" aria-hidden="true">
      <circle cx="8" cy="10" r="3" fill="none" className="stroke-slate-400" strokeWidth="1.5" strokeDasharray="2 2" />
      <circle cx="20" cy="18" r="3" fill="none" className="stroke-slate-400" strokeWidth="1.5" strokeDasharray="2 2" />
      <path d="M10.5 12l7 4.5" className="stroke-stone-300" strokeWidth="1.5" strokeDasharray="2 2" />
    </svg>
  ),
  error: (
    <svg width="28" height="28" viewBox="0 0 28 28" aria-hidden="true">
      <path d="M14 4l11 19H3z" className="fill-closed-50 stroke-closed" strokeWidth="1.6" strokeLinejoin="round" />
      <path d="M14 11v6" className="stroke-closed" strokeWidth="1.8" strokeLinecap="round" />
      <circle cx="14" cy="20" r="1.1" className="fill-closed" />
    </svg>
  ),
}

/**
 * One component for loading, empty and error feedback.
 * Loading/empty use role="status" (polite); errors use role="alert".
 */
export function StatusMessage({ tone, title, children, onRetry, compact = false }) {
  return (
    <div
      role={tone === 'error' ? 'alert' : 'status'}
      className={`mx-auto flex max-w-md flex-col items-center px-4 text-center ${compact ? 'gap-2 py-8' : 'gap-3 py-16'}`}
    >
      {icons[tone]}
      <p className="text-sm font-semibold text-slate-900">{title}</p>
      {children && <div className="text-sm text-slate-600">{children}</div>}
      {onRetry && (
        <Button variant="primary" onClick={onRetry} className="mt-1">
          Retry
        </Button>
      )}
    </div>
  )
}
