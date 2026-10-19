"""OpenStreetMap building points for the comparison cities, from Geofabrik state extracts.

The extracts are large (about 1.2 GB for the four states), so they are downloaded by hand into
tmp/osm/ (deletable) and this step keeps only what the analysis needs: one point inside each
building (way or multipolygon relation tagged building=*, assembled by osmium) within the city's 2020 Census boundary, written
to data/raw/manual/osm/<city>.parquet with a provenance file. Run once per extract:

    uv run python -m historic_preservation.fetch.osm
"""

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import duckdb
import pandas as pd

from historic_preservation.config import CENSUS_PLACES, MANUAL, NORMALIZED

TMP = Path(__file__).resolve().parents[3] / "tmp" / "osm"
OUT = MANUAL / "osm"
STATES = {"Washington": "district-of-columbia", "New York": "new-york", "Philadelphia": "pennsylvania",
          "Boston": "massachusetts"}


def extract(city: str) -> Path:
    """The newest dated extract for the city's state, checked against Geofabrik's md5."""
    files = sorted(TMP.glob(f"{STATES[city]}-[0-9]*.osm.pbf"))
    if not files:
        raise FileNotFoundError(f"no {STATES[city]} extract in {TMP}")
    pbf = files[-1]
    want = Path(f"{pbf}.md5").read_text().split()[0]
    got = hashlib.md5(pbf.read_bytes()).hexdigest()
    if got != want:
        raise ValueError(f"{pbf.name}: md5 {got} != {want}")
    return pbf


def boundary(city: str, path: Path) -> None:
    places = pd.read_parquet(NORMALIZED / "comps_places.parquet")
    geom = json.loads(places.loc[places["geoid"] == CENSUS_PLACES[city], "geometry"].iloc[0])
    path.write_text(json.dumps({"type": "FeatureCollection",
                                "features": [{"type": "Feature", "properties": {}, "geometry": geom}]}))


def buildings(city: str) -> None:
    pbf = extract(city)
    slug = STATES[city]
    work = TMP / slug
    work.mkdir(exist_ok=True)
    boundary(city, work / "boundary.geojson")
    clipped, tagged = work / "city.osm.pbf", work / "buildings.osm.pbf"
    subprocess.run(["osmium", "extract", "--no-progress", "-p", str(work / "boundary.geojson"), "-s", "smart", "-O",
                    "-o", str(clipped), str(pbf)], check=True)
    subprocess.run(["osmium", "tags-filter", "-O", "-o", str(tagged), str(clipped), "w/building", "r/building"],
                   check=True)
    seq, config = work / "buildings.geojsonl", work / "export.json"
    # Only the building tag: other tags vary in case ('ref', 'REF'), which DuckDB reads as duplicate columns.
    config.write_text(json.dumps({"attributes": {"type": True, "id": True}, "include_tags": ["building"]}))
    subprocess.run(["osmium", "export", "--no-progress", "-O", "-f", "geojsonseq", "--geometry-types=polygon",
                    "-c", str(config), "-o", str(seq), str(tagged)], check=True)
    con = duckdb.connect()
    con.install_extension("spatial")
    con.load_extension("spatial")
    # osmium assembles building ways and multipolygon relations into (multi)polygons.
    df = con.execute(f"""
        SELECT "@type" AS osm_type, "@id" AS osm_id, building,
               ST_X(ST_PointOnSurface(geom)) AS lon, ST_Y(ST_PointOnSurface(geom)) AS lat
        FROM ST_Read('{seq}')
        WHERE building IS NOT NULL
    """).df()
    OUT.mkdir(parents=True, exist_ok=True)
    df.to_parquet(OUT / f"{slug}.parquet", index=False)
    (OUT / f"{slug}.json").write_text(json.dumps({
        "city": city, "extract": pbf.name, "md5": Path(f"{pbf}.md5").read_text().split()[0],
        "source": f"https://download.geofabrik.de/north-america/us/{pbf.name}",
        "clip": "2020 Census place boundary (TIGERweb)", "buildings": len(df),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "license": "OpenStreetMap contributors, ODbL",
    }, indent=1))
    print(f"  {city}: {len(df):,} buildings")


if __name__ == "__main__":
    for c in STATES:
        buildings(c)
