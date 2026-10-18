"""Project paths and source registry."""

import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
INPUTS = ROOT / "inputs"
DATA = ROOT / "data"
RAW = DATA / "raw"
NORMALIZED = DATA / "normalized"
JOINED = DATA / "joined"
ANALYSIS = DATA / "analysis"
CHARTS_OUT = ROOT / "charts" / "out"

USER_AGENT = (
    "dc-historic-preservation-research/0.1 "
    "(public-interest data analysis; polite crawler, >=1s between requests)"
)
MIN_INTERVAL_S = 1.0

ARCGIS_BASE = "https://maps2.dcgis.dc.gov/dcgis/rest/services"


@dataclass(frozen=True)
class ArcGISLayer:
    key: str
    path: str
    out_fields: tuple[str, ...] | None = None  # None means all fields
    geometry: bool = False


ARCGIS_LAYERS = (
    ArcGISLayer(
        "zoning_lookup",
        "DCOZ/Zone_Mapservice/MapServer/56",
        (
            "OBJECTID", "SSL", "SQUARE", "SUFFIX", "LOT", "PREMISEADD",
            "WARD_ID", "ANC_ID", "ZONING", "ZONE_DISTRICT", "ZR58",
            "OVERLAY_SHORT", "HISTORICDISTRICT_NAME", "HISTORICLANDMARK_LABEL",
        ),
    ),
    # Owner names are fetched into the raw snapshot only; normalize drops them.
    ArcGISLayer(
        "itspe",
        "DCGIS_DATA/Property_and_Land_WebMercator/MapServer/53",
        (
            "OBJECTID", "INTERNALID", "SSL", "SQUARE", "SUFFIX", "LOT",
            "PRESSL", "PIPARENTLOT", "PROPTYPE", "USECODE", "CLASSTYPE",
            "TAXRATE", "MIXEDUSE", "HSTDCODE", "OWNOCCT", "COOPUNITS",
            "PCHILDCODE", "ABTLOTCODE", "LANDAREA", "PREMISEADD",
            "UNITNUMBER", "NBHD", "NBHDNAME", "PRMS_WARD", "OWNERNAME",
            "OWNNAME2", "NEWLAND", "NEWIMPR", "NEWTOTAL", "ASSESSMENT",
            "SALEPRICE", "SALEDATE", "DEEDDATE", "EXTRACTDAT", "ANNUALTAX",
        ),
    ),
    # Condo unit SSL -> underlying lot (MAT_SSL); replaces the square-majority guess.
    ArcGISLayer(
        "condo_relate",
        "DCGIS_DATA/Property_and_Land_WebMercator/MapServer/52",
        (
            "OBJECTID", "SSL", "SQUARE", "SUFFIX", "LOT", "REGIME", "REGIME_ID",
            "COMPLEX", "NAME", "REC_LOT", "TAX_LOT", "AIR_LOT", "MAT_SSL", "O_LOTS",
        ),
    ),
    # Condo regimes that sit on more than one lot.
    ArcGISLayer("condo_one_to_many", "DCGIS_DATA/Property_and_Land_WebMercator/MapServer/55"),
    ArcGISLayer("historic_districts", "DCGIS_DATA/Historic_WebMercator/MapServer/6", geometry=True),
    ArcGISLayer(
        "landmark_points",
        "DCGIS_DATA/Planning_Landuse_and_Zoning_WebMercator/MapServer/22",
        geometry=True,
    ),
    ArcGISLayer(
        "landmark_polygons",
        "DCGIS_DATA/Planning_Landuse_and_Zoning_WebMercator/MapServer/23",
        geometry=True,
    ),
    ArcGISLayer(
        "potential_landmarks",
        "DCGIS_DATA/Planning_Landuse_and_Zoning_WebMercator/MapServer/26",
        geometry=True,
    ),
    ArcGISLayer(
        "preservation_easements",
        "DCGIS_DATA/Planning_Landuse_and_Zoning_WebMercator/MapServer/43",
        geometry=True,
    ),
)


def snapshot_dir() -> Path:
    """The raw snapshot the build reads: $HP_SNAPSHOT, else the newest complete one."""
    if name := os.environ.get("HP_SNAPSHOT"):
        return RAW / name
    complete = sorted(p.parent for p in RAW.glob("*/SNAPSHOT_COMPLETE"))
    if not complete:
        raise FileNotFoundError(f"No complete snapshot under {RAW}; run `make fetch`.")
    return complete[-1]
