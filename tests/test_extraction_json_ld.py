from pathlib import Path

from app.services.extraction.json_ld import extract_json_ld_job_posting

FIXTURES = Path(__file__).parent / "fixtures"


def _load(name: str) -> str:
    return (FIXTURES / name).read_text()


def test_single_object():
    result = extract_json_ld_job_posting(_load("json_ld_single.html"))
    assert result is not None
    assert "Data Analyst" in result["text"]
    assert "SQL" in result["text"]
    assert result["hints"]["title"] == "Data Analyst"
    assert result["hints"]["hiringOrganization"] == "Acme GmbH"
    assert result["hints"]["employmentType"] == "FULL_TIME"


def test_list_of_objects_finds_job_posting():
    result = extract_json_ld_job_posting(_load("json_ld_list.html"))
    assert result is not None
    assert "Airflow" in result["text"]
    assert result["hints"]["hiringOrganization"] == "Beta AG"


def test_at_graph_wrapper():
    result = extract_json_ld_job_posting(_load("json_ld_graph.html"))
    assert result is not None
    assert "LLM applications" in result["text"]


def test_skips_broken_block_and_finds_valid_one():
    result = extract_json_ld_job_posting(_load("json_ld_broken_then_valid.html"))
    assert result is not None
    assert "analytics team" in result["text"]


def test_only_broken_json_returns_none():
    assert extract_json_ld_job_posting(_load("json_ld_only_broken.html")) is None


def test_no_json_ld_at_all_returns_none():
    assert extract_json_ld_job_posting("<html><body>No scripts here.</body></html>") is None
