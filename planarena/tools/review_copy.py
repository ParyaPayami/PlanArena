"""Build the anonymised copy of the repository for double-blind review (Computational Urban Science).

Reviewers see the code through an Anonymous GitHub mirror (anonymous.4open.science/r/planarena-cus). The mirror can
replace listed words in text files but not inside PDFs or images, so this builds a copy that is anonymous by itself,
as one commit on the branch `cus-review`, from the committed tree at HEAD:

- left out: every PDF (the manuscript and Online Resource 1 are uploaded to the journal), the files that exist only
  for the author (title page, cover letter, submission checklist, talk, paper outline, the Hugging Face deployment)
  and the responses to earlier reviews;
- replaced in every remaining text file: the author's name, affiliation, user name and local paths, and the links
  to the public repository;
- then every file, text or binary, and every path is searched for the identifying words, and the build stops if
  one remains.

The working tree and main are not touched. This file is itself left out of the copy, since it lists the words.

Run:  python -I -m planarena.tools.review_copy [--keep DIR]    then:  git push origin cus-review
"""
from __future__ import annotations

import argparse
import io
import os
import re
import shutil
import subprocess
import tarfile
import tempfile
from pathlib import Path

from planarena.config import ROOT

BRANCH = "cus-review"
ANON_REPO = "https://anonymous.4open.science/r/planarena-cus"

DROP = [re.compile(p) for p in (
    r".*\.pdf",
    r"paper/cus/(title_page\.tex(\.in)?|cover_letter\.md|README\.md)",
    r"docs/(PAPER_OUTLINE|REVIEW_RESPONSE(_\d+)?)\.md",
    r"docs/talks/.*",
    r"deploy/.*",
    r"planarena/tools/review_copy\.py",
)]

# (file, old, new): each must match, so a change upstream stops the build instead of leaking
REPLACE = [
    ("LICENSE", "Copyright (c) 2026 Parya Payami",
     "Copyright (c) 2026 the author (name withheld for double-blind review)"),
    ("paper/paper.tex.in", "\\author{\\normalsize Parya Payami\\\\ \\footnotesize Department of Architecture, "
     "University of Wisconsin--Milwaukee}", "\\author{\\normalsize Anonymous author (withheld for double-blind review)}"),
    ("planarena/paper.py", 'PUBLIC_REPO = "https://github.com/ParyaPayami/PlanArena"', f'PUBLIC_REPO = "{ANON_REPO}"'),
    ("README.md", "- **Paper and technical supplement:** [paper/paper.pdf](paper/paper.pdf), "
     "[paper/supplement.pdf](paper/supplement.pdf).",
     "- **Paper:** this is the anonymised copy for double-blind review, without PDFs. "
     "`python -I -m planarena.paper` builds the manuscript and Online Resource 1 in `paper/cus/`."),
    ("README.md", "| Review response | [docs/REVIEW_RESPONSE.md](docs/REVIEW_RESPONSE.md): each reviewer comment "
     "mapped to the change, its test and the evidence file |\n", ""),
    ("planarena/tools/check_refs.py", "The PIMALUOS submission was rejected because references had real-looking DOIs "
     "that resolved to different papers.", "A reference can carry a real-looking DOI that resolves to a different paper."),
    ("tests/test_check_refs.py", "must catch the PIMALUOS failure mode:", "must catch the main failure mode:"),
    ("planarena/models/integration.py", "The question (PAPER_OUTLINE, contribution 1):",
     "The question (the paper's first contribution):"),
    ("planarena/tools/pack_demo.py", ", for the hosted demo (deploy/huggingface).", ", for the hosted demo."),
]
SAME_IN = {"paper/paper.tex.in": ["paper/paper.tex", "paper/supplement.tex.in", "paper/supplement.tex"]}

README = """# Computational Urban Science version

This is the anonymised copy of the repository for double-blind review. The PDFs, the title page and the cover letter
are left out; the manuscript and Online Resource 1 are uploaded to the journal.

`python -I -m planarena.paper` builds `manuscript.tex` and `online_resource_1.tex` here from `results/` and the
`.tex.in` templates (and their PDFs, when tectonic is installed). The figures are in `figures/`.
"""

WORDS = ("payami", "parya", "wisconsin", "schermer", "pimaluos")  # anywhere, in any file or path
TEXT_WORDS = re.compile(r"\buwm\b", re.I)  # whole word, text files only (bytes in binaries can spell it)


def _git(*args, cwd=ROOT, env=None) -> str:
    return subprocess.run(["git", *args], cwd=cwd, env=env, check=True, capture_output=True, text=True).stdout.strip()


def _text(p: Path) -> str | None:
    b = p.read_bytes()
    if b"\0" in b:
        return None
    try:
        return b.decode("utf-8")
    except UnicodeDecodeError:
        return None


def build(out: Path, ref: str = "HEAD") -> list[str]:
    """Write the anonymised tree of `ref` into `out` (empty or new); returns the paths left out."""
    out.mkdir(parents=True, exist_ok=True)
    tar = subprocess.run(["git", "archive", "--format=tar", ref], cwd=ROOT, check=True, capture_output=True).stdout
    with tarfile.open(fileobj=io.BytesIO(tar)) as t:
        t.extractall(out, filter="data")
    files = sorted(str(p.relative_to(out)) for p in out.rglob("*") if p.is_file())
    dropped = [f for f in files if any(d.fullmatch(f) for d in DROP)]
    for f in dropped:
        (out / f).unlink()
    for d in sorted({p.parent for p in out.rglob("*")}, key=lambda p: -len(p.parts)):
        if d != out and d.is_dir() and not any(d.iterdir()):
            d.rmdir()

    local = str(ROOT) + "/"
    for p in (p for p in out.rglob("*") if p.is_file()):
        s = _text(p)
        if s is not None and local in s:
            p.write_text(s.replace(local, ""))  # absolute paths recorded by the pipeline become repository-relative
    for f, old, new in REPLACE:
        for g in [f, *SAME_IN.get(f, [])]:
            p = out / g
            s = p.read_text()
            if old not in s:
                raise SystemExit(f"review copy: expected text not found in {g}: {old[:60]!r}")
            p.write_text(s.replace(old, new))
    (out / "paper" / "cus" / "README.md").write_text(README)

    found = []
    for p in sorted(out.rglob("*")):
        rel = str(p.relative_to(out))
        if any(w in rel.lower() for w in WORDS):
            found.append(f"{rel} (path)")
        if not p.is_file():
            continue
        b = p.read_bytes().lower()
        found += [f"{rel}: {w}" for w in WORDS if w.encode() in b]
        s = _text(p)
        if s is not None and TEXT_WORDS.search(s):
            found.append(f"{rel}: uwm")
    if found:
        raise SystemExit("review copy still identifies the author:\n  " + "\n  ".join(found))
    return dropped


def commit(tree: Path, message: str) -> str | None:
    """Commit `tree` on BRANCH (after its last commit, so pushes fast-forward); None when nothing changed."""
    with tempfile.TemporaryDirectory() as tmp:
        env = {**os.environ, "GIT_INDEX_FILE": str(Path(tmp) / "index")}
        git_dir = str(ROOT / ".git")
        _git("--git-dir", git_dir, "--work-tree", str(tree), "add", "-A", "-f", ".", cwd=tree, env=env)
        tree_id = _git("--git-dir", git_dir, "write-tree", cwd=tree, env=env)
    try:
        parent = _git("rev-parse", "--verify", "--quiet", f"refs/heads/{BRANCH}")
    except subprocess.CalledProcessError:
        parent = None
    if parent and _git("rev-parse", f"{parent}^{{tree}}") == tree_id:
        return None
    new = _git("commit-tree", tree_id, *(["-p", parent] if parent else []), "-m", message)
    _git("update-ref", f"refs/heads/{BRANCH}", new, *([parent] if parent else []))
    return new


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--keep", type=Path, help="also keep the copy in this (new) directory")
    ap.add_argument("--message", help="commit message")
    a = ap.parse_args()
    if _git("status", "--porcelain", "--untracked-files=no"):
        print("note: uncommitted changes are not in the copy (it is built from HEAD)")
    head = _git("rev-parse", "--short", "HEAD")
    with tempfile.TemporaryDirectory() as tmp:
        tree = Path(tmp) / "copy"
        dropped = build(tree)
        n = sum(1 for p in tree.rglob("*") if p.is_file())
        new = commit(tree, a.message or f"Anonymised copy for double-blind review (from {head})")
        if a.keep:
            shutil.copytree(tree, a.keep)
    print(f"{n} files, {len(dropped)} left out ({sum(f.endswith('.pdf') for f in dropped)} PDFs); no identifying word")
    print(f"{BRANCH}: {new[:7]} from {head}" if new else f"{BRANCH}: unchanged")


if __name__ == "__main__":
    main()
