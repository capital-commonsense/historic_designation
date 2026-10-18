"""DC Court of Appeals opinions on historic preservation, found via CourtListener search.

The search API works without a token; opinion text does not, so opinion PDFs
are downloaded from each result's source `download_url` (usually dccourts.gov).
"""

import hashlib
import json
from pathlib import Path

import httpx

from historic_preservation.fetch.http import PoliteClient

SEARCH = "https://www.courtlistener.com/api/rest/v4/search/"
QUERIES = (
    '"Preservation League"',
    '"Don\'t Tear It Down"',
    '"Mayor\'s Agent" AND "historic preservation"',
    '"Historic Preservation Review Board"',
    '"Committee of 100 on the Federal City"',
)


def fetch_opinions(client: PoliteClient, dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    results_path = dest / "search_results.json"
    if not results_path.exists():
        clusters: dict[str, dict] = {}
        for q in QUERIES:
            url, params = SEARCH, {"q": q, "type": "o", "court": "dc"}
            while url:
                page = client.get_json(url, params)
                for r in page["results"]:
                    r.setdefault("matched_queries", [])
                    clusters.setdefault(str(r["cluster_id"]), r)["matched_queries"].append(q)
                url, params = page.get("next"), None
        results_path.write_text(json.dumps(clusters, indent=1))
    clusters = json.loads(results_path.read_text())

    manifest_path = dest / "manifest.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    for cid, r in clusters.items():
        for op in r.get("opinions", []):
            name = f"{cid}_{op['id']}.pdf"
            src = op.get("download_url")
            if name in manifest:
                continue
            if not src:
                manifest[name] = {"cluster_id": cid, "status": "no source url"}
                continue
            try:
                body = client.get(src).content
            except httpx.HTTPError as e:
                manifest[name] = {"cluster_id": cid, "url": src, "status": f"error: {e}"}
                continue
            (dest / name).write_bytes(body)
            manifest[name] = {"cluster_id": cid, "url": src, "sha256": hashlib.sha256(body).hexdigest()}
            manifest_path.write_text(json.dumps(manifest, indent=1))
    manifest_path.write_text(json.dumps(manifest, indent=1))
    print(f"  courtlistener: {len(clusters)} cases, {sum('sha256' in m for m in manifest.values())} opinion PDFs")
