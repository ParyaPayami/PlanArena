"""The paper's numbers come from the result files and its citations from the verified bibliography."""
import hashlib
import re

from planarena import paper
from planarena.config import ROOT
from planarena.tools.check_refs import parse_bib


def test_paper_is_current():
    text = paper.render()  # raises if a placeholder has no value
    assert "@@" not in text
    assert paper.OUT.read_text() == text, "run: python -I -m planarena.paper"


def test_every_citation_is_in_the_bibliography():
    keys = {e["key"] for e in parse_bib((ROOT / "docs" / "refs.bib").read_text())}
    cited = paper.citations(paper.TEMPLATE.read_text())
    assert cited and cited <= keys, f"not in refs.bib: {sorted(cited - keys)}"


def test_no_number_is_typed_into_the_text():
    """Results enter the text only through placeholders: no decimals in the template's prose."""
    body = paper.TEMPLATE.read_text().split("\\section{Introduction}")[1].split("\\bibliographystyle")[0]
    body = re.sub(r"\\begin\{figure\}.*?\\end\{figure\}", "", body, flags=re.S)
    assert not re.findall(r"(?<![\w@.])\d+\.\d+(?![\w@])", body.replace("0.04", "")), "decimal typed into the text"


def test_supplement_is_current():
    text = paper.render_supplement()  # raises if a placeholder has no value
    assert "@@" not in text
    assert paper.SUPP_OUT.read_text() == text, "run: python -I -m planarena.paper"
    keys = {e["key"] for e in parse_bib((ROOT / "docs" / "refs.bib").read_text())}
    assert paper.citations(paper.SUPP_TEMPLATE.read_text()) <= keys


# SHA-256 of the lower-case words that would identify the author (name, user name, university, advisor), kept as
# hashes so that this file, too, names no one in the anonymised review copy (planarena.tools.review_copy)
IDENTIFYING = {
    "09f0b20c30a9bcf6e1786cf34465d44f69d811844f454dac89deb5f52a6df1cc",
    "0a47ddc57674d83ca6d220f83e5e86143f1824b6ffa0b3db13605776e0985022",
    "4426272a72f4b4cae28d4263409cbcc495c3545ba3c17e8d293e8644e94dbdc2",
    "e21019b5be0d917b55d9a3b8900ab3be66569f00bce3991b5f158a63900aa3a3",
    "701392d6e9b9065cd6b1a0bdce93e0e5b6c07bf28349560408cd07f2510143ce",
    "d0c400eec55a51590683f87204bc1b5e2e6fceef8ebac262cc750601b366ad19",
    "e33e6c094a4ae25d044f54b846eca56f3c1a4686759e6d4b433ef984664de5d5",
}


def _identifying(text: str) -> set[str]:
    return {w for w in set(re.findall(r"[a-z]+", text.lower())) if hashlib.sha256(w.encode()).hexdigest() in IDENTIFYING}


def test_cus_version_is_current_and_anonymous():
    """The Computational Urban Science files are current, and the manuscript and Online Resource 1 reveal no author
    (double-blind review); only the title page names the author."""
    for path, text in paper.render_cus().items():
        assert "@@" not in text
        assert path.read_text() == text, f"run: python -I -m planarena.paper ({path.name})"
        if path.name != "title_page.tex":
            assert not _identifying(text), path.name


def test_cus_tables_and_figures_are_cited_in_order():
    text = (paper.CUS / "manuscript.tex").read_text().split("\\begin{document}")[1]
    for kind in ("tab", "fig"):
        labels = re.findall(r"\\label\{(%s:[^}]+)\}" % kind, text)
        first = []
        for k in re.findall(r"\\ref\{(%s:[^}]+)\}" % kind, text):
            if k not in first:
                first.append(k)
        assert first == labels, (kind, first, labels)
