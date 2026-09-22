import trafilatura


def extract_main_content(html: str) -> str | None:
    """Main-content extraction fallback (section 7.2.3)."""
    return trafilatura.extract(html, include_comments=False, include_tables=False)
