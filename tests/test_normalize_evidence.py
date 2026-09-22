from app.services.normalize import normalize_for_evidence, normalize_key


def test_evidence_matches_across_case_and_whitespace():
    surface = "fließende  Deutschkenntnisse"
    text = "Wir erwarten FLIESSENDE... nein: fließende deutschkenntnisse (C1)."
    assert normalize_for_evidence(surface) in normalize_for_evidence(text)


def test_evidence_keeps_plus_hash_dot():
    assert normalize_for_evidence("C++") == "c++"
    assert normalize_for_evidence("C#") == "c#"
    assert normalize_for_evidence("Node.js") == "node.js"


def test_evidence_strips_other_punctuation():
    assert normalize_for_evidence("SQL, Python!") == "sql python"


def test_canonical_key_strips_only_trailing_punctuation():
    assert normalize_key("Power BI") == "power bi"
    assert normalize_key("C++.") == "c++"
    assert normalize_key("  Node.js  ") == "node.js"
