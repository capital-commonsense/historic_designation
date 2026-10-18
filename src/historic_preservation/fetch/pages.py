"""Save listed web pages as HTML, plus the PDFs they link to (one level deep)."""

import hashlib
import json
import re
from pathlib import Path
from urllib.parse import unquote, urljoin, urlsplit

import httpx

from historic_preservation.config import WebPage
from historic_preservation.fetch.http import PoliteClient


def _save(client: PoliteClient, url: str, path: Path, manifest: dict) -> bytes | None:
    if path.name in manifest:
        return path.read_bytes() if path.exists() else None
    try:
        body = client.get(url).content
    except httpx.HTTPError as e:
        manifest[path.name] = {"url": url, "status": f"error: {e}"}
        return None
    path.write_bytes(body)
    manifest[path.name] = {"url": url, "sha256": hashlib.sha256(body).hexdigest(), "bytes": len(body)}
    return body


def fetch_pages(client: PoliteClient, pages: tuple[WebPage, ...], dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "linked").mkdir(exist_ok=True)
    manifest_path = dest / "manifest.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    for page in pages:
        ext = ".pdf" if page.url.lower().endswith(".pdf") else ".html"
        html = _save(client, page.url, dest / f"{page.key}{ext}", manifest)
        manifest_path.write_text(json.dumps(manifest, indent=1))
        if not (html and page.follow_pdfs):
            continue
        for href in sorted(set(re.findall(r'href="([^"]+\.pdf)"', html.decode("utf-8", "ignore")))):
            url = urljoin(page.url, href)
            name = re.sub(r"[^A-Za-z0-9._-]+", "_", unquote(urlsplit(url).path.rsplit("/", 1)[-1]))
            _save(client, url, dest / "linked" / name, manifest)
            manifest[name]["linked_from"] = page.key
            manifest_path.write_text(json.dumps(manifest, indent=1))
    print(f"  pages: {sum('sha256' in m for m in manifest.values())} saved, "
          f"{sum('status' in m for m in manifest.values())} failed")
