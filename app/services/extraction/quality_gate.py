import re

LOGIN_WALL_MARKERS = [
    "sign in",
    "log in to",
    "join linkedin",
    "anmelden",
    "einloggen",
    "captcha",
    "access denied",
    "enable javascript",
    "javascript aktivieren",
]

MAX_CHARS = 20_000

_WHITESPACE_RE = re.compile(r"[ \t]+")
_BLANK_LINES_RE = re.compile(r"\n{3,}")


def passes_quality_gate(text: str) -> bool:
    words = text.split()
    if len(words) < 150:
        return False
    if len(words) < 400:
        lowered = text.lower()
        if any(marker in lowered for marker in LOGIN_WALL_MARKERS):
            return False
    return True


def clean_text(text: str) -> tuple[str, bool]:
    """Normalize whitespace, keep line breaks between sections, cap length.

    Returns (cleaned_text, was_truncated).
    """
    lines = [_WHITESPACE_RE.sub(" ", line).strip() for line in text.splitlines()]
    cleaned = "\n".join(lines)
    cleaned = _BLANK_LINES_RE.sub("\n\n", cleaned).strip()

    truncated = len(cleaned) > MAX_CHARS
    if truncated:
        cleaned = cleaned[:MAX_CHARS]
    return cleaned, truncated
