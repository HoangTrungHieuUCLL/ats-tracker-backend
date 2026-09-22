import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass

import httpx
from bs4 import BeautifulSoup

_GREENHOUSE_RE = re.compile(
    r"^https?://(?:boards|job-boards)\.greenhouse\.io/([^/]+)/jobs/(\d+)", re.IGNORECASE
)
_LEVER_RE = re.compile(r"^https?://jobs\.lever\.co/([^/]+)/([0-9a-fA-F-]+)", re.IGNORECASE)
_PERSONIO_RE = re.compile(
    r"^https?://([a-zA-Z0-9-]+)\.jobs\.personio\.de/job/(\d+)", re.IGNORECASE
)


@dataclass
class AtsMatch:
    adapter: str  # "greenhouse" | "lever" | "personio"
    fetch_url: str


def match_ats(url: str) -> AtsMatch | None:
    """Match a job posting URL against known ATS public APIs (section 7.2.2)."""
    if m := _GREENHOUSE_RE.match(url):
        board, job_id = m.group(1), m.group(2)
        return AtsMatch(
            adapter="greenhouse",
            fetch_url=f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs/{job_id}?content=true",
        )
    if m := _LEVER_RE.match(url):
        company, posting_id = m.group(1), m.group(2)
        return AtsMatch(
            adapter="lever",
            fetch_url=f"https://api.lever.co/v0/postings/{company}/{posting_id}",
        )
    if m := _PERSONIO_RE.match(url):
        company, job_id = m.group(1), m.group(2)
        return AtsMatch(
            adapter="personio",
            fetch_url=f"https://{company}.jobs.personio.de/xml",
        )
    return None


def _html_to_text(html: str) -> str:
    return BeautifulSoup(html, "lxml").get_text(separator="\n")


async def fetch_ats_text(client: httpx.AsyncClient, match: AtsMatch, url: str) -> str | None:
    """Fetch and parse the ATS adapter's text. Returns None if the fetch/parse fails."""
    try:
        response = await client.get(match.fetch_url, timeout=20)
        response.raise_for_status()
    except httpx.HTTPError:
        return None

    if match.adapter == "greenhouse":
        return _parse_greenhouse(response)
    if match.adapter == "lever":
        return _parse_lever(response)
    if match.adapter == "personio":
        job_id = _PERSONIO_RE.match(url).group(2)
        return _parse_personio(response, job_id)
    return None


def _parse_greenhouse(response: httpx.Response) -> str | None:
    try:
        data = response.json()
    except ValueError:
        return None
    content = data.get("content")
    return _html_to_text(content) if content else None


def _parse_lever(response: httpx.Response) -> str | None:
    try:
        data = response.json()
    except ValueError:
        return None

    parts = []
    if data.get("descriptionPlain"):
        parts.append(data["descriptionPlain"])
    elif data.get("description"):
        parts.append(_html_to_text(data["description"]))

    for item in data.get("lists") or []:
        text = item.get("plain") or (item.get("content") and _html_to_text(item["content"]))
        if text:
            parts.append(text)

    if data.get("additionalPlain"):
        parts.append(data["additionalPlain"])

    return "\n\n".join(parts) if parts else None


def _parse_personio(response: httpx.Response, job_id: str) -> str | None:
    try:
        root = ET.fromstring(response.content)
    except ET.ParseError:
        return None

    for position in root.findall("position"):
        id_el = position.find("id")
        if id_el is None or (id_el.text or "").strip() != job_id:
            continue
        return _position_text(position)
    return None


def _position_text(position: ET.Element) -> str:
    parts = []
    for elem in position.iter():
        text = (elem.text or "").strip()
        if not text:
            continue
        if "<" in text and ">" in text:
            text = _html_to_text(text)
        parts.append(text)
    return "\n\n".join(parts)
