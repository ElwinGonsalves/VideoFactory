"""Download Natural Earth 1:110m countries (public domain) and slim it for the Remotion map scene.

Keeps geometry (rounded to 0.01 degrees), ISO A3 code and name. Output:
studio/public/geo/countries.geojson (~200 KB). Usage: python scripts/fetch_geo.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import requests

ROOT = Path(__file__).resolve().parent.parent
URL = "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_110m_admin_0_countries.geojson"
OUT = ROOT / "studio" / "public" / "geo" / "countries.geojson"


def _round(coords: Any) -> Any:
    if isinstance(coords, (int, float)):
        return round(float(coords), 2)
    return [_round(c) for c in coords]


def slim(data: dict[str, Any]) -> dict[str, Any]:
    feats = []
    for f in data["features"]:
        p = f["properties"]
        # ISO_A3 is "-99" for France, Norway and a few others; ADM0_A3 is always set.
        code = p.get("ISO_A3") if p.get("ISO_A3") not in (None, "-99") else p.get("ADM0_A3")
        geom = f["geometry"]
        feats.append(
            {
                "type": "Feature",
                "properties": {"iso": code, "name": p.get("NAME", "")},
                "geometry": {"type": geom["type"], "coordinates": _round(geom["coordinates"])},
            }
        )
    return {"type": "FeatureCollection", "features": feats}


def main() -> int:
    res = requests.get(URL, timeout=60)
    res.raise_for_status()
    out = slim(res.json())
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, separators=(",", ":")), encoding="utf-8")
    print(f"{len(out['features'])} countries -> {OUT} ({OUT.stat().st_size // 1024} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
