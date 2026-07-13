// Must stay in sync with the name validator on UserCreate in backend/main.py:
// letters (any unicode script, so accented/non-Latin names are allowed),
// spaces, hyphens, and apostrophes only — no digits or other symbols.
const NAME_PATTERN = /^[\p{L} '-]+$/u

export function isValidName(name) {
  const trimmed = name.trim()
  if (!trimmed || trimmed !== name) return false
  return NAME_PATTERN.test(name)
}

export const NAME_VALIDATION_MESSAGE = 'Name can only contain letters, spaces, hyphens, and apostrophes.'
