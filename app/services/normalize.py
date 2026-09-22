import re
import unicodedata

_TRAILING_PUNCT_RE = re.compile(r"[.,;:!?]+$")
_WHITESPACE_RE = re.compile(r"\s+")
_EVIDENCE_STRIP_RE = re.compile(r"[^\w\s+#.]", re.UNICODE)


def normalize_key(text: str) -> str:
    """Casefold, trim, collapse whitespace, strip trailing punctuation.

    Used for keyword canonical_key / alias_key matching (section 7.5.3).
    """
    text = unicodedata.normalize("NFC", text)
    text = text.casefold().strip()
    text = _WHITESPACE_RE.sub(" ", text)
    text = _TRAILING_PUNCT_RE.sub("", text)
    return text


def normalize_for_evidence(text: str) -> str:
    """Casefold, NFC, collapse whitespace, strip punctuation except `+ # .`.

    Used for the keyword evidence check (section 7.5.2): a keyword counts as
    found when its normalized surface form is a substring of the
    normalized job text.
    """
    text = unicodedata.normalize("NFC", text).casefold()
    text = _EVIDENCE_STRIP_RE.sub("", text)
    text = _WHITESPACE_RE.sub(" ", text).strip()
    return text
