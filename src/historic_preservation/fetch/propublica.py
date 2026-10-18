"""DCPL Form 990 filings via the ProPublica Nonprofit Explorer API."""

import hashlib
import json
from pathlib import Path

import httpx

from historic_preservation.config import DCPL_EIN
from historic_preservation.fetch.http import PoliteClient

API = "https://projects.propublica.org/nonprofits/api/v2/organizations/{ein}.json"


def fetch_filings(client: PoliteClient, dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    org_path = dest / "organization.json"
    if not org_path.exists():
        org_path.write_text(json.dumps(client.get_json(API.format(ein=DCPL_EIN)), indent=1))
    org = json.loads(org_path.read_text())
    manifest_path = dest / "manifest.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    for f in org["filings_with_data"] + org["filings_without_data"]:
        url = f.get("pdf_url")
        if not url:
            continue
        form = f.get("formtype_str") or {0: "990", 1: "990EZ", 2: "990PF"}.get(f.get("formtype"), "990")
        name = f"{f['tax_prd']}_{form}.pdf"
        if name in manifest:
            continue
        try:
            body = client.get(url).content
        except httpx.HTTPStatusError as e:
            # ProPublica blocks scripted PDF downloads (403); record it and move on.
            print(f"  dcpl_990 {name}: HTTP {e.response.status_code}, not downloaded")
            blocked = dest / "blocked.json"
            entries = json.loads(blocked.read_text()) if blocked.exists() else {}
            entries[name] = {"url": url, "status": e.response.status_code}
            blocked.write_text(json.dumps(entries, indent=1))
            continue
        (dest / name).write_bytes(body)
        manifest[name] = {"url": url, "tax_prd": f["tax_prd"], "sha256": hashlib.sha256(body).hexdigest()}
        manifest_path.write_text(json.dumps(manifest, indent=1))
        print(f"  dcpl_990 {name}: {len(body):,} bytes")
