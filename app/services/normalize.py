import re
import unicodedata

_TRAILING_PUNCT_RE = re.compile(r"[.,;:!?]+$")
_WHITESPACE_RE = re.compile(r"\s+")


def normalize_key(text: str) -> str:
    """Casefold, trim, collapse whitespace, strip trailing punctuation.

    Used for keyword canonical_key / alias_key matching (section 7.5).
    """
    text = unicodedata.normalize("NFC", text)
    text = text.casefold().strip()
    text = _WHITESPACE_RE.sub(" ", text)
    text = _TRAILING_PUNCT_RE.sub("", text)
    return text
