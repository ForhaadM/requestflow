# Must stay in sync with frontend/src/lib/nameValidation.js.
NAME_VALIDATION_MESSAGE = "Name can only contain letters, spaces, hyphens, and apostrophes."


def is_valid_name(name: str) -> bool:
    """Letters (any unicode script, so accented/non-Latin names are allowed),
    spaces, hyphens, and apostrophes only — no digits or other symbols, and
    no leading/trailing whitespace."""
    if not name or name != name.strip():
        return False
    return all(c.isalpha() or c in " '-" for c in name)
