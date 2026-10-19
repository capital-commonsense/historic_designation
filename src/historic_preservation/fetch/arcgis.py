"""Page DC GIS ArcGIS REST layers into a raw snapshot.

Each layer gets a folder with the layer metadata, the server's record count,
one JSON file per page (written once, so an interrupted fetch resumes), and a
COMPLETE marker recording what was fetched.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

from historic_preservation.config import ArcGISLayer
from historic_preservation.fetch.http import PoliteClient


def _write_json(path: Path, data) -> None:
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data))
    tmp.rename(path)


def fetch_layer(client: PoliteClient, layer: ArcGISLayer, dest: Path) -> None:
    out = dest / layer.key
    if (out / "COMPLETE.json").exists():
        print(f"  {layer.key}: already complete, skipping")
        return
    out.mkdir(parents=True, exist_ok=True)
    url = f"{layer.base}/{layer.path}"

    spatial = ({"geometry": ",".join(map(str, layer.envelope)), "geometryType": "esriGeometryEnvelope",
                "inSR": 4326, "spatialRel": "esriSpatialRelIntersects"} if layer.envelope else {})
    meta = client.get_json(url, {"f": "json"})
    _write_json(out / "layer.json", meta)
    count = client.get_json(f"{url}/query", {"where": layer.where, "returnCountOnly": "true", "f": "json", **spatial})["count"]
    page_size = meta.get("maxRecordCount") or 1000
    oid = meta.get("objectIdField") or next(
        (f["name"] for f in meta.get("fields", []) if f.get("type") == "esriFieldTypeOID"), "OBJECTID")

    n_features = 0
    for offset in range(0, count, page_size):
        page = out / f"page_{offset:07d}.json"
        if not page.exists():
            data = client.get_json(
                f"{url}/query",
                {
                    "where": layer.where,
                    **spatial,
                    **({"maxAllowableOffset": layer.simplify} if layer.simplify else {}),
                    "outFields": ",".join(layer.out_fields) if layer.out_fields else "*",
                    "returnGeometry": str(layer.geometry).lower(),
                    "orderByFields": oid,
                    "resultOffset": offset,
                    "resultRecordCount": page_size,
                    **({"outSR": 4326, "geometryPrecision": 7, "f": "geojson"} if layer.geometry else {"f": "json"}),
                },
            )
            _write_json(page, data)
        n_features += len(json.loads(page.read_text())["features"])
        print(f"  {layer.key}: {min(offset + page_size, count):,}/{count:,}", end="\r")
    print()

    if n_features != count:
        raise RuntimeError(f"{layer.key}: fetched {n_features} features, server count {count}")
    _write_json(
        out / "COMPLETE.json",
        {
            "url": url,
            "server_count": count,
            "features": n_features,
            "page_size": page_size,
            "out_fields": list(layer.out_fields) if layer.out_fields else "*",
            "geometry": layer.geometry,
            "where": layer.where,
            "completed_at": datetime.now(timezone.utc).isoformat(),
        },
    )


def read_features(snapshot: Path, key: str) -> list[dict]:
    """All features of a fetched layer, in page order, as {"attributes", "geometry"}.

    Geometry layers are GeoJSON (attributes under "properties"); others are Esri JSON.
    """
    pages = sorted((snapshot / "arcgis" / key).glob("page_*.json"))
    return [
        {"attributes": f.get("attributes", f.get("properties")), "geometry": f.get("geometry")}
        for p in pages
        for f in json.loads(p.read_text())["features"]
    ]
