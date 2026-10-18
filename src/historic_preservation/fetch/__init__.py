"""Fetch stage: write raw, dated snapshots under data/raw/<YYYY-MM-DD>/."""

from datetime import date

from historic_preservation.config import ARCGIS_LAYERS, DOCUMENTS, RAW, WEB_PAGES
from historic_preservation.fetch.arcgis import fetch_layer
from historic_preservation.fetch.courtlistener import fetch_opinions
from historic_preservation.fetch.dcoz import fetch_zc_cases
from historic_preservation.fetch.documents import fetch_document
from historic_preservation.fetch.hprb import fetch_hprb
from historic_preservation.fetch.http import PoliteClient
from historic_preservation.fetch.pages import fetch_pages
from historic_preservation.fetch.propublica import fetch_filings


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
        fetch_filings(client, dest / "dcpl_990")
        fetch_opinions(client, dest / "court_opinions")
        fetch_pages(client, WEB_PAGES, dest / "web")
        fetch_hprb(client, dest / "hprb")
        fetch_zc_cases(client, dest / "dcoz", range(2000, date.today().year + 1))
    finally:
        client.close()
    (dest / "SNAPSHOT_COMPLETE").touch()
