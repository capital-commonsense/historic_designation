"""Fetch stage: write raw, dated snapshots under data/raw/<YYYY-MM-DD>/."""

from datetime import date

from historic_preservation.config import ARCGIS_LAYERS, RAW
from historic_preservation.fetch.arcgis import fetch_layer
from historic_preservation.fetch.http import PoliteClient


def run() -> None:
    # A same-day rerun resumes today's folder; earlier snapshots are never touched.
    dest = RAW / date.today().isoformat()
    print(f"Fetching into {dest}")
    client = PoliteClient()
    try:
        for layer in ARCGIS_LAYERS:
            fetch_layer(client, layer, dest / "arcgis")
    finally:
        client.close()
    (dest / "SNAPSHOT_COMPLETE").touch()
