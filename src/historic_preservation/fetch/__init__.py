"""Fetch stage: write raw, dated snapshots under data/raw/<YYYY-MM-DD>/."""

from datetime import date

from historic_preservation.config import ARCGIS_LAYERS, DOCUMENTS, RAW
from historic_preservation.fetch.arcgis import fetch_layer
from historic_preservation.fetch.documents import fetch_document
from historic_preservation.fetch.http import PoliteClient


def run() -> None:
    # A same-day rerun resumes today's folder; earlier snapshots are never touched.
    dest = RAW / date.today().isoformat()
    print(f"Fetching into {dest}")
    client = PoliteClient()
    try:
        for layer in ARCGIS_LAYERS:
            fetch_layer(client, layer, dest / "arcgis")
        for doc in DOCUMENTS:
            fetch_document(client, doc, dest / "documents")
    finally:
        client.close()
    (dest / "SNAPSHOT_COMPLETE").touch()
