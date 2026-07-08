export function ClaimToggle({ claimed, claimantName, canToggle, submitting, onToggle }) {
  return (
    <div className="flex items-center gap-2" onClick={(e) => e.stopPropagation()}>
      <button
        type="button"
        onClick={canToggle ? onToggle : undefined}
        disabled={!canToggle || submitting}
        aria-pressed={claimed}
        title={canToggle ? (claimed ? 'Unclaim this request' : 'Claim this request') : undefined}
        className={`relative h-6 w-11 shrink-0 rounded-full transition-colors duration-300 ${
          claimed ? 'bg-slate-900' : 'bg-slate-300'
        } ${canToggle ? 'cursor-pointer' : 'cursor-default opacity-70'} disabled:cursor-not-allowed disabled:opacity-50`}
      >
        <span
          className={`absolute top-0.5 left-0.5 h-5 w-5 rounded-full bg-white shadow transition-transform duration-300 ease-in-out ${
            claimed ? 'translate-x-5' : 'translate-x-0'
          }`}
        />
      </button>
      <span className="whitespace-nowrap text-xs font-medium text-slate-600">
        {claimed ? `Claimed by: ${claimantName}` : 'Unclaimed'}
      </span>
    </div>
  )
}
