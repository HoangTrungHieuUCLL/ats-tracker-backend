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

# ponytail: fixed phrase list, not a general boilerplate detector — extend when
# a new source's trailing chrome (Xing, Stepstone, Indeed, ...) shows up in raw_text.
TRAILING_BOILERPLATE_MARKERS = [
    "ähnliche jobs",
    "ähnliche suchen",
    "ebenfalls angesehen",
    "wen kennen sie bereits",
    "mit einer empfehlung",
    "top-inhalte auf linkedin",
    "weitere jobs",
    "jobs für sie",
    "people also viewed",
    "similar jobs",
    "related jobs",
    "you may also like",
]

_WHITESPACE_RE = re.compile(r"[ \t]+")
_BLANK_LINES_RE = re.compile(r"\n{3,}")
_BOILERPLATE_RE = re.compile(
    "|".join(re.escape(marker) for marker in TRAILING_BOILERPLATE_MARKERS), re.IGNORECASE
)


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

    match = _BOILERPLATE_RE.search(cleaned)
    if match:
        cleaned = cleaned[: match.start()].strip()

    truncated = len(cleaned) > MAX_CHARS
    if truncated:
        cleaned = cleaned[:MAX_CHARS]
    return cleaned, truncated
