"""The reference checker must catch the main failure mode: a real DOI attached to an invented paper."""
from planarena.tools.check_refs import check_entry, parse_bib

BIB = """
@article{real2024,
  author = {Liu, Wei and Dou, Ming},
  title = {Exploring the impacts of heterogeneity and stochasticity in air-conditioning behavior},
  journal = {Sustainable Cities and Society},
  year = {2024},
  doi = {10.1016/j.scs.2024.105285}
}
@article{fake2024,
  author = {Li, M. and others},
  title = {Consensus-based multi-agent reinforcement learning for participatory urban planning},
  journal = {Sustainable Cities and Society},
  year = {2024},
  doi = {10.1016/j.scs.2024.105285}
}
@book{noid, author = {Someone}, title = {A book without an identifier}, year = {2020}}
"""

RECORD = {"title": "Exploring the impacts of heterogeneity and stochasticity in air-conditioning behavior",
          "first_family": "liu", "year": 2024, "container": "Sustainable Cities and Society"}
FAKE_RESOLVER = {"doi": lambda d: RECORD, "arxiv": lambda a: None, "isbn": lambda i: None}


def test_parse_bib():
    e = parse_bib(BIB)
    assert [x["key"] for x in e] == ["real2024", "fake2024", "noid"]
    assert e[0]["doi"] == "10.1016/j.scs.2024.105285" and e[1]["author"].startswith("Li, M.")


def test_fabricated_entry_with_real_doi_fails_and_real_entry_passes():
    real, fake, noid = parse_bib(BIB)
    assert check_entry(real, FAKE_RESOLVER)["status"] == "ok"
    r = check_entry(fake, FAKE_RESOLVER)
    assert r["status"] == "mismatch" and "title differs" in r["details"] and "first author differs" in r["details"]
    assert check_entry(noid, FAKE_RESOLVER)["status"] == "unverifiable"


def test_edited_book_is_checked_by_its_editors():
    book = parse_bib("@book{h, editor = {Brandt, Felix and Conitzer, Vincent}, title = {Handbook of Computational Social "
                     "Choice}, year = {2016}, doi = {10.1017/CBO9781107446984}}")[0]
    rec = {"title": "Handbook of Computational Social Choice", "first_family": "moulin", "first_editor": "brandt",
           "year": 2016, "container": ""}  # the record lists the foreword's author first
    resolve = {"doi": lambda d: rec, "arxiv": lambda a: None, "isbn": lambda i: None}
    assert check_entry(book, resolve)["status"] == "ok"
    assert check_entry({**book, "editor": "Someone, Else"}, resolve)["status"] == "mismatch"


def test_family_name_particles_are_ignored():
    from planarena.tools.check_refs import first_family
    assert first_family("te Brömmelstroet, Marco") == first_family("Brömmelstroet, Marco te") == "brommelstroet"
    assert first_family("Waddell, Paul and Borning, Alan") == "waddell"
