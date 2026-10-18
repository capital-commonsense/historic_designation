"""Download source documents (PDFs) into a raw snapshot, with a hash manifest."""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from historic_preservation.config import Document
from historic_preservation.fetch.http import PoliteClient


def fetch_document(client: PoliteClient, doc: Document, dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    path = dest / doc.filename
    meta_path = dest / f"{doc.filename}.json"
    if meta_path.exists():
        print(f"  {doc.key}: already fetched, skipping")
        return
    body = client.get(doc.url).content
    path.write_bytes(body)
    meta_path.write_text(
        json.dumps(
            {
                "key": doc.key,
                "url": doc.url,
                "sha256": hashlib.sha256(body).hexdigest(),
                "bytes": len(body),
                "fetched_at": datetime.now(timezone.utc).isoformat(),
            },
            indent=2,
        )
    )
    print(f"  {doc.key}: {len(body):,} bytes")


def document_path(snapshot: Path, doc: Document) -> Path:
    return snapshot / "documents" / doc.filename
