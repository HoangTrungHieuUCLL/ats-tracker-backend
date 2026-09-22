from app.services.url_normalize import normalize_url


def test_lowercases_scheme_and_host():
    normalized, domain = normalize_url("HTTPS://Example.COM/jobs/123")
    assert normalized == "https://example.com/jobs/123"
    assert domain == "example.com"


def test_strips_trailing_slash_and_fragment():
    normalized, _ = normalize_url("https://example.com/jobs/123/#apply")
    assert normalized == "https://example.com/jobs/123"


def test_removes_tracking_params_but_keeps_others():
    normalized, _ = normalize_url(
        "https://boards.greenhouse.io/acme/jobs/123?gh_jid=123&utm_source=li&utm_campaign=x&trk=abc"
    )
    assert normalized == "https://boards.greenhouse.io/acme/jobs/123?gh_jid=123"


def test_linkedin_jobs_view_drops_entire_query_string():
    normalized, _ = normalize_url(
        "https://www.linkedin.com/jobs/view/1234567890/?refId=abc&trackingId=xyz"
    )
    assert normalized == "https://www.linkedin.com/jobs/view/1234567890"


def test_rejects_non_http_scheme():
    assert normalize_url("ftp://example.com/jobs/1") is None


def test_rejects_missing_host():
    assert normalize_url("not a url") is None


def test_dedupe_equivalence():
    a, _ = normalize_url("https://example.com/jobs/1?utm_source=x")
    b, _ = normalize_url("https://EXAMPLE.com/jobs/1/?utm_source=y")
    assert a == b
