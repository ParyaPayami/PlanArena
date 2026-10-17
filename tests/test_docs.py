"""Reported numbers must come from result files: the generated docs must match what planarena.report produces."""
from planarena import report


def test_docs_are_current():
    stale = [p.name for p, text in report.outputs().items() if p.read_text() != text]
    assert not stale, f"run: python -I -m planarena.report  (out of date: {stale})"
