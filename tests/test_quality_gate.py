from app.services.extraction.quality_gate import clean_text, passes_quality_gate

LONG_TEXT = " ".join(["word"] * 200)
SHORT_TEXT = " ".join(["word"] * 50)


def test_fails_under_150_words():
    assert passes_quality_gate(SHORT_TEXT) is False


def test_passes_150_plus_words_without_login_markers():
    assert passes_quality_gate(LONG_TEXT) is True


def test_fails_under_400_words_with_login_marker():
    text = "Please sign in to view this job posting. " + LONG_TEXT
    assert passes_quality_gate(text) is False


def test_passes_400_plus_words_even_with_login_marker():
    text = "Please sign in to continue. " + " ".join(["word"] * 450)
    assert passes_quality_gate(text) is True


def test_german_login_markers_detected():
    text = "Bitte zum Fortfahren einloggen. " + LONG_TEXT
    assert passes_quality_gate(text) is False


def test_clean_text_collapses_whitespace_and_blank_lines():
    raw = "Line one   with   spaces\n\n\n\nLine two\t\ttabbed"
    cleaned, truncated = clean_text(raw)
    assert cleaned == "Line one with spaces\n\nLine two tabbed"
    assert truncated is False


def test_clean_text_truncates_at_20000_chars():
    raw = "a" * 25_000
    cleaned, truncated = clean_text(raw)
    assert len(cleaned) == 20_000
    assert truncated is True
