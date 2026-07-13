import { PASSWORD_RULES } from '../lib/passwordRules'

function CheckIcon({ met }) {
  return (
    <svg
      className={`h-4 w-4 shrink-0 transition-colors duration-200 ${met ? 'text-emerald-600' : 'text-red-500'}`}
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
    >
      {met ? (
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
      ) : (
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
      )}
    </svg>
  )
}

export function PasswordRequirements({ password }) {
  return (
    <ul className="mt-2 space-y-1">
      {PASSWORD_RULES.map((rule) => {
        const met = rule.test(password)
        return (
          <li key={rule.id} className="flex items-center gap-2 text-xs">
            <CheckIcon met={met} />
            <span className={`transition-colors duration-200 ${met ? 'text-emerald-700' : 'text-slate-500'}`}>
              {rule.label}
            </span>
          </li>
        )
      })}
    </ul>
  )
}
