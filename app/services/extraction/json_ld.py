import json
from typing import Any

from bs4 import BeautifulSoup


def _iter_candidate_objects(data: Any):
    """Yield every dict found in a JSON-LD payload: single object, list, or @graph."""
    if isinstance(data, dict):
        if "@graph" in data and isinstance(data["@graph"], list):
            yield from _iter_candidate_objects(data["@graph"])
        else:
            yield data
    elif isinstance(data, list):
        for item in data:
            yield from _iter_candidate_objects(item)


def _is_job_posting(obj: dict) -> bool:
    obj_type = obj.get("@type")
    if isinstance(obj_type, str):
        return obj_type == "JobPosting"
    if isinstance(obj_type, list):
        return "JobPosting" in obj_type
    return False


def _html_to_text(html: str) -> str:
    return BeautifulSoup(html, "lxml").get_text(separator="\n")


def extract_json_ld_job_posting(html: str) -> dict | None:
    """Find a JobPosting in <script type="application/ld+json"> blocks (section 7.2.1).

    Returns {"text": ..., "hints": {...}} for the first JobPosting found, or None.
    Malformed JSON blocks are skipped, never raised.
    """
    soup = BeautifulSoup(html, "lxml")
    for script in soup.find_all("script", type="application/ld+json"):
        if not script.string:
            continue
        try:
            data = json.loads(script.string)
        except (json.JSONDecodeError, TypeError):
            continue

        for obj in _iter_candidate_objects(data):
            if not isinstance(obj, dict) or not _is_job_posting(obj):
                continue

            description = obj.get("description") or ""
            text = _html_to_text(description) if description else ""

            hints = {
                "title": obj.get("title"),
                "hiringOrganization": (obj.get("hiringOrganization") or {}).get("name")
                if isinstance(obj.get("hiringOrganization"), dict)
                else obj.get("hiringOrganization"),
                "jobLocation": obj.get("jobLocation"),
                "datePosted": obj.get("datePosted"),
                "validThrough": obj.get("validThrough"),
                "employmentType": obj.get("employmentType"),
            }
            return {"text": text, "hints": hints}

    return None
