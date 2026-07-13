// Must stay in sync with validate_password_strength in backend/password_rules.py.
// Purely client-side UX (live checklist) — the backend enforces the same
// rules independently and is the actual security boundary.
export const PASSWORD_RULES = [
  { id: 'length', label: 'At least 8 characters', test: (pw) => pw.length >= 8 },
  { id: 'uppercase', label: 'One uppercase letter', test: (pw) => /[A-Z]/.test(pw) },
  { id: 'lowercase', label: 'One lowercase letter', test: (pw) => /[a-z]/.test(pw) },
  { id: 'number', label: 'One number', test: (pw) => /[0-9]/.test(pw) },
  { id: 'special', label: 'One special character', test: (pw) => /[^A-Za-z0-9]/.test(pw) },
]

export function isPasswordValid(password) {
  return PASSWORD_RULES.every((rule) => rule.test(password))
}
