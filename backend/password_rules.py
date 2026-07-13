import re

# Must stay in sync with frontend/src/lib/passwordRules.js's live checklist.
# That checklist is UX only — this is the actual security boundary.
PASSWORD_RULES = [
    ("length", "at least 8 characters", lambda pw: len(pw) >= 8),
    ("uppercase", "one uppercase letter", lambda pw: re.search(r"[A-Z]", pw) is not None),
    ("lowercase", "one lowercase letter", lambda pw: re.search(r"[a-z]", pw) is not None),
    ("number", "one number", lambda pw: re.search(r"[0-9]", pw) is not None),
    ("special", "one special character", lambda pw: re.search(r"[^A-Za-z0-9]", pw) is not None),
]


def validate_password_strength(password: str) -> None:
    """Raises ValueError listing every unmet rule, for use in a Pydantic validator."""
    unmet = [description for _, description, test in PASSWORD_RULES if not test(password)]
    if unmet:
        raise ValueError("Password must contain " + ", ".join(unmet) + ".")
