"""APA 7 reference lists with natbib author-year citation keys, for journals that cite by name and year.

Formats the verified bibliography (docs/refs.bib, checked by planarena.tools.check_refs) and the dataset records
(paper/cus/data_refs.yaml, each with the URL the pipeline downloads from) as a LaTeX thebibliography whose entries
natbib cites as (Author, Year): one author "Last", two "Last & Last", three or more "Last et al.". The list is
alphabetical by first author, with a/b suffixes where an in-text label and year repeat. Up to 20 authors are listed,
and DOIs are given as https://doi.org/ links.
"""
from __future__ import annotations

import re

import yaml

from planarena.config import ROOT
from planarena.tools.check_refs import parse_bib

BIB = ROOT / "docs" / "refs.bib"
PARTICLES = {"van", "von", "de", "der", "den", "da", "di", "du", "le", "la", "te", "ter", "ten"}
DATA_REFS = ROOT / "paper" / "cus" / "data_refs.yaml"


def _clean(s: str) -> str:
    s = re.sub(r"\s+", " ", s).strip()
    while s.startswith("{") and s.endswith("}") and _balanced(s[1:-1]):
        s = s[1:-1].strip()
    return s


def _balanced(s: str) -> bool:
    d = 0
    for ch in s:
        d += {"{": 1, "}": -1}.get(ch, 0)
        if d < 0:
            return False
    return d == 0


def _strip_braces(s: str) -> str:
    """Drop BibTeX's case-protecting braces ({GIS} -> GIS) but keep braces that are a LaTeX command's argument."""
    out, stack = [], []
    for ch in s:
        if ch == "{":
            prev = "".join(out)
            keep = bool(re.search(r"\\(?:[A-Za-z]+|[^A-Za-z\s])\s*$", prev)) and not prev.endswith("\\\\")
            stack.append(keep)
            if keep:
                out.append(ch)
        elif ch == "}" and stack:
            if stack.pop():
                out.append(ch)
        else:
            out.append(ch)
    return "".join(out)


def names(field: str) -> list[tuple[str, str]]:
    """BibTeX names -> [(last, initials)]; a braced name ({Agency}) is kept whole."""
    out = []
    for n in re.split(r"\s+and\s+", _clean(field)):
        n = n.strip()
        if n.startswith("{") and n.endswith("}"):
            out.append((n[1:-1], ""))
            continue
        if "," in n:
            last, first = [x.strip() for x in n.split(",", 1)]
        else:
            parts = n.split()
            last, first = parts[-1], " ".join(parts[:-1])
        # particles written after the given name ("Wesemael, Pieter van") belong to the surname
        words = first.split()
        while words and words[-1].lower() in PARTICLES:
            last = f"{words.pop()} {last}"
        out.append((last, _initials(" ".join(words))))
    return out


def _initials(first: str) -> str:
    bits = []
    for w in first.replace(".", ". ").split():
        if "-" in w and not w.startswith("-"):
            bits.append("-".join(_initial(x) for x in w.split("-") if x))
        else:
            bits.append(_initial(w))
    return " ".join(b for b in bits if b)


def _initial(w: str) -> str:
    w = w.strip(".")
    if not w:
        return ""
    m = re.match(r"(\\['`^\"~=.uvHcdbk]\{?\w\}?|\{\\[^}]+\}|\w)", w)
    return (m.group(1) if m else w[0]) + "."


def _authors_apa(ns: list[tuple[str, str]]) -> str:
    fmt = [f"{l}, {i}" if i else l for l, i in ns]
    if len(fmt) > 20:
        fmt = fmt[:19] + ["\\ldots{} " + fmt[-1]]
        return ", ".join(fmt)
    if len(fmt) == 1:
        return fmt[0]
    return ", ".join(fmt[:-1]) + ", \\& " + fmt[-1]


def _label(ns: list[tuple[str, str]]) -> str:
    last = [l for l, _ in ns]
    if len(last) == 1:
        return last[0]
    if len(last) == 2:
        return f"{last[0]} \\& {last[1]}"
    return f"{last[0]} et~al."


def _sort_key(ns, year, title) -> tuple:
    plain = lambda s: re.sub(r"[^a-z]", "", re.sub(r"\\.", "", s.lower()))
    return tuple(plain(l) for l, _ in ns[:3]) + (str(year), plain(title))


def _end(s: str) -> str:
    return s if s.rstrip().endswith(("?", "!", ".")) else s + "."


def entry(e: dict) -> tuple[list, str, str, str]:
    """(names, year, title, formatted APA string without the year disambiguation)."""
    typ = e.get("type", "article")
    title = _strip_braces(_clean(e.get("title", "")))
    year = _clean(e.get("year", "n.d."))
    doi = _clean(e.get("doi", ""))
    link = f" \\url{{https://doi.org/{doi}}}" if doi else (f" \\url{{{e['url']}}}" if e.get("url") else "")
    if typ == "dataset":
        ns = [(e["author"], "")]
        body = (f"{{\\itshape {title}}} [Data set]. " + (f"{_end(e['publisher'])} " if e.get("publisher") else "")
                + f"Retrieved {e.get('retrieved', 'October 2026')}, from \\url{{{e['url']}}}")
        return ns, year, title, body
    if e.get("author"):
        ns = names(e["author"])
        who = None
    else:
        ns = names(e["editor"])
        who = "Ed." if len(ns) == 1 else "Eds."
    pages = _clean(e.get("pages", "")).replace("--", "–").replace("-", "–")
    if typ == "article":
        vol = _clean(e.get("volume", ""))
        num = _clean(e.get("number", ""))
        src = f"{{\\itshape {_strip_braces(_clean(e['journal']))}}}"
        if vol:
            src += f", {{\\itshape {vol}}}" + (f"({num})" if num else "")
        if pages:
            src += f", {pages}"
        body = f"{_end(title)} {src}.{link}"
    elif typ == "book":
        body = f"{{\\itshape {_end(title)}}} {_end(_strip_braces(_clean(e.get('publisher', ''))))}{link}"
    else:  # inproceedings / incollection
        where = f"In {{\\itshape {_strip_braces(_clean(e.get('booktitle', '')))}}}" + (f" (pp. {pages})" if pages else "")
        body = f"{_end(title)} {where}. {_end(_strip_braces(_clean(e.get('publisher', ''))))}{link}"
    return ns, year, title, body, *([who] if who else [])


def bibliography(keys: set[str]) -> str:
    """thebibliography for the cited keys (refs.bib entries and dataset records), APA 7, alphabetical."""
    bib = {e["key"]: e for e in parse_bib(BIB.read_text())}
    data = yaml.safe_load(DATA_REFS.read_text()) if DATA_REFS.exists() else {}
    rows = []
    for k in keys:
        if k in bib:
            e = bib[k]
        elif k in data:
            e = {"type": "dataset", "key": k, **data[k]}
        else:
            raise KeyError(f"no reference for {k}")
        ns, year, title, body, *ed = entry(e)
        rows.append({"key": k, "ns": ns, "year": year, "title": title, "body": body, "ed": ed[0] if ed else None})
    rows.sort(key=lambda r: _sort_key(r["ns"], r["year"], r["title"]))
    seen: dict[tuple, list] = {}
    for r in rows:
        seen.setdefault((_label(r["ns"]), r["year"]), []).append(r)
    for group in seen.values():
        if len(group) > 1:
            for i, r in enumerate(group):
                r["year"] = f"{r['year']}{'abcdefghij'[i]}"
    out = ["\\begin{thebibliography}{}", "\\setlength{\\itemsep}{1pt}"]  # the class prints the heading
    for r in rows:
        who = _authors_apa(r["ns"]) + (f" ({r['ed']})" if r["ed"] else "")
        full = ", ".join(l for l, _ in r["ns"][:6])
        out.append(f"\\bibitem[{{{_label(r['ns'])}}}({r['year']}){{{full}}}]{{{r['key']}}}\n"
                   f"{_end(who) if not who.endswith('.') else who} ({r['year']}). {r['body']}")
    out.append("\\end{thebibliography}")
    return "\n".join(x for x in out if x != "")
