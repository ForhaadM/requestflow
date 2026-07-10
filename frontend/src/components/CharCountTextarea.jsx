export function CharCountTextarea({ value, onChange, maxLength, rows = 4, placeholder, autoFocus }) {
  const remaining = maxLength - value.length

  return (
    <div>
      <textarea
        rows={rows}
        value={value}
        onChange={onChange}
        maxLength={maxLength}
        placeholder={placeholder}
        autoFocus={autoFocus}
        className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500"
      />
      <div className="mt-1 text-right text-xs text-slate-400">
        {remaining} characters remaining
      </div>
    </div>
  )
}
