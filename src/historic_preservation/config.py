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


@dataclass(frozen=True)
class Document:
    key: str
    url: str

    @property
    def filename(self) -> str:
        return f"{self.key}.pdf"


_OP_ATTACH = "https://planning.dc.gov/sites/default/files/dc/sites/op/publication/attachments"

# DC Inventory of Historic Sites: the 2009 alphabetical edition plus annual
# updates listed at https://planning.dc.gov/publication/dc-inventory-updates
INVENTORY_2009 = Document("inventory_2009", f"{_OP_ATTACH}/Inventory%202009%200%20Alpha%20Version%2003%2011.pdf")
INVENTORY_UPDATES = tuple(
    Document(f"inventory_update_fy{fy}", f"{_OP_ATTACH}/{name}")
    for fy, name in (
        (2010, "FY%202010%20Landmarks%20Update.pdf"),
        (2011, "FY%202011%20Landmarks%20Update.pdf"),
        (2012, "FY%202012%20Landmarks%20Update_0.pdf"),
        (2013, "FY%202013%20Landmarks%20Upldate.pdf"),
        (2014, "FY%202014%20Landmarks%20Update.pdf"),
        (2015, "FY%202015%20Landmarks%20Update.pdf"),
        (2016, "FY%202016%20Landmarks%20Update.pdf"),
        (2017, "FY%202017%20Landmarks.pdf"),
        (2018, "FY%202018%20Landmarks.pdf"),
        (2019, "FY%202019%20Landmarks.pdf"),
        (2020, "2020%20Landmarks%20Update.pdf"),
    )
)
# Full HPO annual reports after the last Inventory update (FY2020), and the
# 2021-2025 preservation-plan implementation report.
HPO_REPORTS = (
    Document("hpo_annual_report_fy2021", f"{_OP_ATTACH}/2021%20HPO%20Annual%20Report.pdf"),
    Document("hpo_annual_report_fy2022", f"{_OP_ATTACH}/2022%20Annual%20Report%20FINAL%20corrected.pdf"),
    Document("hp_plan_implementation_2025", f"{_OP_ATTACH}/2025%20HP%20Plan-FINAL%20%20Implementation%20Report.pdf"),
)
DOCUMENTS = (INVENTORY_2009, *INVENTORY_UPDATES, *HPO_REPORTS)


def snapshot_dir() -> Path:
    """The raw snapshot the build reads: $HP_SNAPSHOT, else the newest complete one."""
    if name := os.environ.get("HP_SNAPSHOT"):
        return RAW / name
    complete = sorted(p.parent for p in RAW.glob("*/SNAPSHOT_COMPLETE"))
    if not complete:
        raise FileNotFoundError(f"No complete snapshot under {RAW}; run `make fetch`.")
    return complete[-1]
