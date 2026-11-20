export function SearchInput({ id, label, value, onChange, placeholder }) {
  return (
    <div className="relative w-full sm:w-72">
      <label htmlFor={id} className="sr-only">
        {label}
      </label>
      <svg
        className="pointer-events-none absolute top-1/2 left-3 -translate-y-1/2 text-slate-400"
        width="14"
        height="14"
        viewBox="0 0 16 16"
        aria-hidden="true"
      >
        <circle cx="7" cy="7" r="5" fill="none" stroke="currentColor" strokeWidth="1.7" />
        <path d="M11 11l3.5 3.5" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" />
      </svg>
      <input
        id={id}
        type="search"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        autoComplete="off"
        className="h-9 w-full rounded-md border border-stone-300 bg-white pr-3 pl-9 text-sm text-slate-900 placeholder:text-slate-500 focus:border-accent-600"
      />
    </div>
  )
}
