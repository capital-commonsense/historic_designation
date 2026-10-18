"""DC Court of Appeals opinions on historic preservation, via CourtListener.

Search works without a token. Opinion text needs one: set COURTLISTENER_TOKEN
in the environment or the gitignored .env file. Without a token, only the
search results (case names, dates, docket numbers) are saved.
"""

import hashlib
import json
from pathlib import Path

import httpx

from historic_preservation.config import secret
from historic_preservation.fetch.http import PoliteClient

API = "https://www.courtlistener.com/api/rest/v4"
QUERIES = (
    '"Preservation League"',
    '"Don\'t Tear It Down"',
    '"Mayor\'s Agent" AND "historic preservation"',
    '"Historic Preservation Review Board"',
    '"Committee of 100 on the Federal City"',
)
OPINION_FIELDS = "id,cluster_id,type,author_str,plain_text,html_with_citations,download_url"


def fetch_opinions(client: PoliteClient, dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    token = secret("COURTLISTENER_TOKEN")
    headers = {"Authorization": f"Token {token}"} if token else None

    results_path = dest / "search_results.json"
    if not results_path.exists():
        clusters: dict[str, dict] = {}
        for q in QUERIES:
            url, params = f"{API}/search/", {"q": q, "type": "o", "court": "dc"}
            while url:
                page = client.get_json(url, params, headers)
                for r in page["results"]:
                    r.setdefault("matched_queries", [])
                    clusters.setdefault(str(r["cluster_id"]), r)["matched_queries"].append(q)
                url, params = page.get("next"), None
        results_path.write_text(json.dumps(clusters, indent=1))
    clusters = json.loads(results_path.read_text())
    if not token:
        print(f"  courtlistener: {len(clusters)} cases (no token; opinion text not fetched)")
        return

    manifest_path = dest / "manifest.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    for cid, r in clusters.items():
        for op in r.get("opinions", []):
            name = f"{cid}_{op['id']}.json"
            if name in manifest and "sha256" in manifest[name]:
                continue
            try:
                data = client.get_json(f"{API}/opinions/{op['id']}/", {"fields": OPINION_FIELDS}, headers)
            except (httpx.HTTPError, RuntimeError) as e:
                manifest[name] = {"cluster_id": cid, "status": f"error: {e}"}
                continue
            body = json.dumps(data, indent=1)
            (dest / name).write_text(body)
            manifest[name] = {"cluster_id": cid, "case_name": r.get("caseName"), "date_filed": r.get("dateFiled"),
                              "sha256": hashlib.sha256(body.encode()).hexdigest()}
            manifest_path.write_text(json.dumps(manifest, indent=1))
    manifest_path.write_text(json.dumps(manifest, indent=1))
    print(f"  courtlistener: {len(clusters)} cases, {sum('sha256' in m for m in manifest.values())} opinions")
