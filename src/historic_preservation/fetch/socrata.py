"""Fetch whole Socrata datasets (NYC Open Data) as GeoJSON into a raw snapshot."""

import json
from datetime import datetime, timezone
from pathlib import Path

from historic_preservation.fetch.http import PoliteClient

NYC = "https://data.cityofnewyork.us"
LIMIT = 50000


def fetch_dataset(client: PoliteClient, key: str, dataset_id: str, dest: Path) -> None:
    out = dest / key
    if (out / "COMPLETE.json").exists():
        print(f"  {key}: already complete, skipping")
        return
    out.mkdir(parents=True, exist_ok=True)
    meta = client.get_json(f"{NYC}/api/views/{dataset_id}.json")
    (out / "metadata.json").write_text(json.dumps(meta))
    data = client.get_json(f"{NYC}/resource/{dataset_id}.geojson", {"$limit": LIMIT})
    n = len(data["features"])
    if n >= LIMIT:
        raise RuntimeError(f"{key}: {n} rows hit the {LIMIT} limit; page the request")
    (out / "data.geojson").write_text(json.dumps(data))
    (out / "COMPLETE.json").write_text(json.dumps({
        "dataset": dataset_id, "features": n, "rows_updated_at": meta.get("rowsUpdatedAt"),
        "completed_at": datetime.now(timezone.utc).isoformat()}))
    print(f"  {key}: {n} features")


def fetch_paged(client: PoliteClient, key: str, dataset_id: str, select: str, dest: Path) -> None:
    """A large dataset, some columns only, as GeoJSON pages (page_*.geojson) in row-id order."""
    out = dest / key
    if (out / "COMPLETE.json").exists():
        print(f"  {key}: already complete, skipping")
        return
    out.mkdir(parents=True, exist_ok=True)
    meta = client.get_json(f"{NYC}/api/views/{dataset_id}.json")
    (out / "metadata.json").write_text(json.dumps(meta))
    count = int(client.get_json(f"{NYC}/resource/{dataset_id}.json", {"$select": "count(*)"})[0]["count"])
    n = 0
    for offset in range(0, count, LIMIT):
        page = out / f"page_{offset:07d}.geojson"
        if not page.exists():
            data = client.get_json(f"{NYC}/resource/{dataset_id}.geojson",
                                   {"$select": select, "$order": ":id", "$limit": LIMIT, "$offset": offset})
            page.with_suffix(".tmp").write_text(json.dumps(data))
            page.with_suffix(".tmp").rename(page)
        n += len(json.loads(page.read_text())["features"])
        print(f"  {key}: {min(offset + LIMIT, count):,}/{count:,}", end="\r")
    print()
    if n != count:
        raise RuntimeError(f"{key}: fetched {n} rows, server count {count}")
    (out / "COMPLETE.json").write_text(json.dumps({
        "dataset": dataset_id, "select": select, "features": n, "rows_updated_at": meta.get("rowsUpdatedAt"),
        "completed_at": datetime.now(timezone.utc).isoformat()}))
