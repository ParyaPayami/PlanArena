"""Package the data the PlanArena server needs at run time, for the hosted demo (deploy/huggingface).

Copies, with paths kept relative to the repository root, into exports/demo_data/ (git-ignored):
  data/processed/            the Manhattan demo twin and its model layers
  web/public/data/           the Manhattan web layers
  data/cities/registry.json  the city list
  data/cities/<id>/          each city's twin, except its history/ snapshots and its web/tiles/ cache (tiles are
                             rebuilt on demand)
Nothing from data/raw/ is included: no source download, and no owner, mailing or taxpayer field (those are never
requested). Writes MANIFEST.json with each file's size and SHA-256.

Run:  python -I -m planarena.tools.pack_demo
"""
from __future__ import annotations

import hashlib
import json
import shutil

from planarena.config import DATA, PROCESSED, ROOT, WEB_DATA
from planarena.national.common import CITIES

OUT = ROOT / "exports" / "demo_data"
SKIP_DIRS = {"history", "tiles"}


def _sha(p) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def files():
    for base in (PROCESSED, WEB_DATA):
        yield from (p for p in base.rglob("*") if p.is_file())
    yield CITIES / "registry.json"
    for city in sorted(d for d in CITIES.iterdir() if d.is_dir()):
        for p in city.rglob("*"):
            rel = p.relative_to(city).parts
            if p.is_file() and not SKIP_DIRS & set(rel[:-1]) and p.name != ".DS_Store":
                yield p


def main() -> dict:
    if OUT.exists():
        shutil.rmtree(OUT)
    manifest, total = {}, 0
    for p in files():
        rel = p.relative_to(ROOT)
        dst = OUT / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, dst)
        manifest[str(rel)] = {"bytes": p.stat().st_size, "sha256": _sha(p)}
        total += p.stat().st_size
    (OUT / "MANIFEST.json").write_text(json.dumps({"files": len(manifest), "bytes": total, "data_root": str(DATA.relative_to(ROOT)),
                                                   "files_detail": manifest}, indent=1))
    print(f"{len(manifest):,} files, {total / 1e9:.2f} GB -> {OUT.relative_to(ROOT)}")
    return manifest


if __name__ == "__main__":
    main()
