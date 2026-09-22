from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

_TRACKING_EXACT = {
    "gclid",
    "fbclid",
    "mc_cid",
    "mc_eid",
    "trk",
    "trackingid",
    "refid",
    "ref",
    "src",
    "source",
}


def _is_tracking_param(key: str) -> bool:
    key_lower = key.lower()
    return key_lower.startswith("utm_") or key_lower in _TRACKING_EXACT


def normalize_url(raw_url: str) -> tuple[str, str] | None:
    """Normalize a job posting URL for dedupe (section 5).

    Returns (normalized_url, domain), or None if the URL is invalid.
    """
    try:
        parts = urlsplit(raw_url.strip())
    except ValueError:
        return None

    scheme = parts.scheme.lower()
    if scheme not in ("http", "https") or not parts.netloc:
        return None

    host = parts.netloc.lower()
    path = parts.path
    if len(path) > 1 and path.endswith("/"):
        path = path.rstrip("/")

    if host == "linkedin.com" or host == "www.linkedin.com":
        if path.startswith("/jobs/view/"):
            query = ""
        else:
            query = _filtered_query(parts.query)
    else:
        query = _filtered_query(parts.query)

    normalized = urlunsplit((scheme, host, path, query, ""))
    return normalized, host


def _filtered_query(raw_query: str) -> str:
    pairs = parse_qsl(raw_query, keep_blank_values=True)
    kept = [(k, v) for k, v in pairs if not _is_tracking_param(k)]
    return urlencode(kept)
