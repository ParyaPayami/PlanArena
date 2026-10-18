"""Download a public ArcGIS REST feature layer (FeatureServer or MapServer) to GeoParquet, with provenance.

Pages through the layer by object id in parallel, keeps only the requested fields (owner and mailing fields are
never requested), records URL, fields, feature count, retrieval date and SHA-256 next to the file (SOURCE.json).
Downloaded data is untrusted: read it with python -I.
"""
from __future__ import annotations

import json
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from planarena.national.common import record

PRIVATE = ("OWNER", "OWN_", "MAIL", "TAXPAYER")  # never requested, whatever a caller asks for


def _get(url: str, params: dict) -> dict:
    cmd = ["curl", "-sfL", "-m", "300", "-A", "Mozilla/5.0", "-G", url]
    for k, v in params.items():
        cmd += ["--data-urlencode", f"{k}={v}"]
    for attempt in range(3):
        r = subprocess.run(cmd, capture_output=True)
        if r.returncode == 0:
            d = json.loads(r.stdout)
            if "error" not in d:
                return d
    raise RuntimeError(f"{url}: {r.stderr.decode()[:200] or d.get('error')}")


def layer_info(url: str) -> dict:
    return _get(url, {"f": "json"})


def fetch_layer(url: str, out: Path, fields: list[str], where: str = "1=1", workers: int = 8):
    """GeoDataFrame (EPSG:4326) of a layer, cached at ``out`` (GeoParquet)."""
    import geopandas as gpd
    import pandas as pd

    if out.exists():
        return gpd.read_parquet(out)
    fields = [f for f in fields if not f.upper().startswith(PRIVATE)]
    info = layer_info(url)
    oid = info.get("objectIdField") or next(f["name"] for f in info["fields"] if f["type"] == "esriFieldTypeOID")
    page = int(info.get("maxRecordCount") or 1000)
    ids = _get(url + "/query", {"where": where, "returnIdsOnly": "true", "f": "json"})["objectIds"] or []
    ids = sorted(ids)
    chunks = [ids[i:i + page] for i in range(0, len(ids), page)]

    def one(chunk):
        d = _get(url + "/query", {"where": f"{oid} >= {chunk[0]} AND {oid} <= {chunk[-1]} AND ({where})",
                                  "outFields": ",".join(fields), "outSR": "4326", "f": "geojson",
                                  "resultRecordCount": str(page)})
        return gpd.GeoDataFrame.from_features(d.get("features", []), crs=4326)

    with ThreadPoolExecutor(workers) as ex:
        parts = list(ex.map(one, chunks))
    g = gpd.GeoDataFrame(pd.concat([p for p in parts if len(p)], ignore_index=True), crs=4326)
    out.parent.mkdir(parents=True, exist_ok=True)
    g.to_parquet(out)
    record(out, url, {"where": where, "outFields": ",".join(fields)}, features=int(len(g)), expected=len(ids),
           layer=info.get("name"))
    return g
