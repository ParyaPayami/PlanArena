"""Reported numbers must come from result files: the generated docs must match what planarena.report produces."""
from planarena import report


def test_docs_are_current():
    stale = [p.name for p, text in report.outputs().items() if p.read_text() != text]
    assert not stale, f"run: python -I -m planarena.report  (out of date: {stale})"


def test_every_reference_is_reviewed_and_logged():
    """Each bibliography entry appears in the citation log (the author fills in read_by), and nothing else does."""
    import csv

    from planarena.config import ROOT
    from planarena.tools.check_refs import parse_bib

    keys = {e["key"] for e in parse_bib((ROOT / "docs" / "refs.bib").read_text())}
    with open(ROOT / "docs" / "citation_log.csv", newline="") as f:
        logged = {r["citekey"] for r in csv.DictReader(f)}
    assert keys == logged, f"in bib only: {sorted(keys - logged)}; in log only: {sorted(logged - keys)}"
