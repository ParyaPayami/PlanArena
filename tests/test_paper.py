"""The paper's numbers come from the result files and its citations from the verified bibliography."""
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
