import httpx
import pytest
import respx

from app.services.extraction.ats_adapters import fetch_ats_text, match_ats


def test_matches_greenhouse_boards_url():
    match = match_ats("https://boards.greenhouse.io/acme/jobs/123456")
    assert match is not None
    assert match.adapter == "greenhouse"
    assert match.fetch_url == "https://boards-api.greenhouse.io/v1/boards/acme/jobs/123456?content=true"


def test_matches_greenhouse_job_boards_url():
    match = match_ats("https://job-boards.greenhouse.io/acme/jobs/123456")
    assert match is not None
    assert match.adapter == "greenhouse"


def test_matches_lever_url():
    match = match_ats("https://jobs.lever.co/acme/5ac21346-8e0c-4494-8e7a-3eb92ff77902")
    assert match is not None
    assert match.adapter == "lever"
    assert (
        match.fetch_url
        == "https://api.lever.co/v0/postings/acme/5ac21346-8e0c-4494-8e7a-3eb92ff77902"
    )


def test_matches_personio_url():
    match = match_ats("https://acme.jobs.personio.de/job/4103")
    assert match is not None
    assert match.adapter == "personio"
    assert match.fetch_url == "https://acme.jobs.personio.de/xml"


def test_non_ats_url_does_not_match():
    assert match_ats("https://www.linkedin.com/jobs/view/12345") is None


@pytest.mark.asyncio
@respx.mock
async def test_fetch_greenhouse_text():
    url = "https://boards.greenhouse.io/acme/jobs/123456"
    match = match_ats(url)
    respx.get(match.fetch_url).mock(
        return_value=httpx.Response(200, json={"content": "<p>We need a Data Engineer.</p>"})
    )
    async with httpx.AsyncClient() as client:
        text = await fetch_ats_text(client, match, url)
    assert text is not None
    assert "Data Engineer" in text


@pytest.mark.asyncio
@respx.mock
async def test_fetch_lever_text():
    url = "https://jobs.lever.co/acme/5ac21346-8e0c-4494-8e7a-3eb92ff77902"
    match = match_ats(url)
    respx.get(match.fetch_url).mock(
        return_value=httpx.Response(
            200,
            json={
                "descriptionPlain": "We are hiring a Data Analyst.",
                "lists": [{"plain": "Requirement: SQL"}],
            },
        )
    )
    async with httpx.AsyncClient() as client:
        text = await fetch_ats_text(client, match, url)
    assert text is not None
    assert "Data Analyst" in text
    assert "Requirement: SQL" in text


@pytest.mark.asyncio
@respx.mock
async def test_fetch_personio_text():
    url = "https://acme.jobs.personio.de/job/4103"
    match = match_ats(url)
    xml_body = """<?xml version="1.0" encoding="UTF-8"?>
<workzag-jobs>
  <position>
    <id>4103</id>
    <name>AI Engineer Working Student</name>
    <jobDescriptions>
      <jobDescription>
        <name>Your tasks</name>
        <value><![CDATA[<p>Build and evaluate LLM prompts.</p>]]></value>
      </jobDescription>
    </jobDescriptions>
  </position>
  <position>
    <id>9999</id>
    <name>Unrelated Job</name>
  </position>
</workzag-jobs>"""
    respx.get(match.fetch_url).mock(
        return_value=httpx.Response(
            200, content=xml_body.encode(), headers={"Content-Type": "application/xml"}
        )
    )
    async with httpx.AsyncClient() as client:
        text = await fetch_ats_text(client, match, url)
    assert text is not None
    assert "AI Engineer Working Student" in text
    assert "Unrelated Job" not in text
