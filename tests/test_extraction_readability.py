from pathlib import Path

from app.services.extraction.quality_gate import passes_quality_gate
from app.services.extraction.readability import extract_main_content

FIXTURES = Path(__file__).parent / "fixtures"


def test_extracts_main_article_and_drops_nav_chrome():
    html = (FIXTURES / "readability_article.html").read_text()
    text = extract_main_content(html)

    assert text is not None
    assert "Data Analyst" in text
    assert "pandas and numpy" in text
    assert "Sign in" not in text
    assert "cookies" not in text.lower()
    assert passes_quality_gate(text)
