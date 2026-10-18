"""HPRB meeting records from planning.dc.gov's publication listing (keyword "HPRB").

Saves the listing pages, each publication page, and the PDFs attached to it.
Older meetings (c. 2008-2012) are HTML pages with the actions inline; newer
ones attach "HPRB Actions" / agenda PDFs.
"""

import hashlib
import json
import re
from pathlib import Path
from urllib.parse import unquote, urljoin, urlsplit

import httpx

from historic_preservation.fetch.http import PoliteClient

BASE = "https://planning.dc.gov"
LISTING = f"{BASE}/publications"
# Attachments worth keeping: meeting actions/agendas/notices and designation
# cases. Permit-case staff reports (the bulk of each meeting) are skipped.
KEEP = re.compile(r"action|agenda|notice|nominat|landmark_nom|designation|case_\d|amendment|expansion|boundary",
                  re.I)


def _safe(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", name)


def fetch_hprb(client: PoliteClient, dest: Path, keyword: str = "HPRB") -> None:
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "pages").mkdir(exist_ok=True)
    (dest / "attachments").mkdir(exist_ok=True)
    index_path = dest / "index.json"
    index = json.loads(index_path.read_text()) if index_path.exists() else {}

    if not index.get("listing_complete"):
        slugs: list[str] = []
        page = 0
        while True:
            html = client.get(LISTING, {"keys": keyword, "page": page}).text
            found = sorted(set(re.findall(r'href="/publication/([^"?#]+)"', html)))
            if not found:
                break
            slugs += [s for s in found if s not in slugs]
            page += 1
        index = {"listing_complete": True, "keyword": keyword, "slugs": slugs, "files": {}}
        index_path.write_text(json.dumps(index, indent=1))

    for slug in index["slugs"]:
        page_file = dest / "pages" / f"{_safe(slug)}.html"
        if page_file.name not in index["files"]:
            try:
                html = client.get(f"{BASE}/publication/{slug}").text
            except httpx.HTTPError as e:
                index["files"][page_file.name] = {"slug": slug, "status": f"error: {e}"}
                continue
            page_file.write_text(html)
            index["files"][page_file.name] = {"slug": slug, "sha256": hashlib.sha256(html.encode()).hexdigest()}
            index_path.write_text(json.dumps(index, indent=1))
        html = page_file.read_text() if page_file.exists() else ""
        for href in sorted(set(re.findall(r'href="([^"]+/publication/attachments/[^"]+)"', html))):
            url = urljoin(BASE, href)
            name = _safe(unquote(urlsplit(url).path.rsplit("/", 1)[-1]))
            if name in index["files"] or not KEEP.search(name):
                continue
            try:
                body = client.get(url).content
            except httpx.HTTPError as e:
                index["files"][name] = {"url": url, "slug": slug, "status": f"error: {e}"}
                continue
            (dest / "attachments" / name).write_bytes(body)
            index["files"][name] = {"url": url, "slug": slug, "sha256": hashlib.sha256(body).hexdigest()}
            index_path.write_text(json.dumps(index, indent=1))
    index_path.write_text(json.dumps(index, indent=1))
    n_ok = sum("sha256" in f for f in index["files"].values())
    print(f"  hprb: {len(index['slugs'])} publications, {n_ok} files saved")
