/** Compact page header: title, one line of context, optional controls. */
export function PageHeader({ title, meta, children }) {
  return (
    <header className="flex flex-wrap items-center justify-between gap-x-6 gap-y-3 border-b border-stone-200 bg-white px-4 py-3 sm:px-6">
      <div className="min-w-0">
        <h1
          id="page-title"
          tabIndex={-1}
          className="text-lg font-semibold tracking-tight text-slate-900 focus:outline-none"
        >
          {title}
        </h1>
        {meta && <p className="text-sm text-slate-600">{meta}</p>}
      </div>
      {children && <div className="flex w-full flex-wrap items-center gap-2 sm:w-auto">{children}</div>}
    </header>
  )
}
