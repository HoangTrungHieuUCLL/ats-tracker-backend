import httpx

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
ACCEPT_LANGUAGE = "de-DE,de;q=0.9,en;q=0.8"
MAX_RESPONSE_BYTES = 5 * 1024 * 1024
FETCH_TIMEOUT_SECONDS = 20
BLOCKED_STATUS_CODES = {401, 403, 429, 999}


class FetchBlocked(Exception):
    """Login wall / bot-blocked response (section 7.1). Not retried."""


class FetchTransientError(Exception):
    """5xx, timeout, or other transient failure. Retried with backoff."""


class FetchTooLarge(Exception):
    """Response exceeded the 5 MB cap. Not retried."""


async def fetch_page(client: httpx.AsyncClient, url: str) -> str:
    headers = {"User-Agent": USER_AGENT, "Accept-Language": ACCEPT_LANGUAGE}
    try:
        async with client.stream(
            "GET", url, headers=headers, timeout=FETCH_TIMEOUT_SECONDS, follow_redirects=True
        ) as response:
            if response.status_code in BLOCKED_STATUS_CODES:
                raise FetchBlocked(f"HTTP {response.status_code}")
            if response.status_code >= 400:
                raise FetchTransientError(f"HTTP {response.status_code}")

            chunks = bytearray()
            async for chunk in response.aiter_bytes():
                chunks.extend(chunk)
                if len(chunks) > MAX_RESPONSE_BYTES:
                    raise FetchTooLarge("response exceeded 5 MB")

            encoding = response.encoding or "utf-8"
            return bytes(chunks).decode(encoding, errors="replace")
    except httpx.TimeoutException as exc:
        raise FetchTransientError("timeout") from exc
    except httpx.HTTPError as exc:
        raise FetchTransientError(str(exc)) from exc
