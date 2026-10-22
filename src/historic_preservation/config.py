"""Project paths and source registry."""

import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
INPUTS = ROOT / "inputs"
DATA = ROOT / "data"
RAW = DATA / "raw"
MANUAL = RAW / "manual"  # hand-downloaded files (see records_request/manual_fetch.md)
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
    geometry: bool = False  # fetched as GeoJSON in WGS84 (EPSG:4326)
    where: str = "1=1"
    base: str = ARCGIS_BASE  # other cities' servers for the comparison layers
    envelope: tuple[float, float, float, float] | None = None  # WGS84 xmin, ymin, xmax, ymax filter
    simplify: float | None = None  # maxAllowableOffset, in output units (degrees for GeoJSON)


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
    # Lot polygons for spatial joins (same layer, geometry only).
    ArcGISLayer("lot_polygons", "DCOZ/Zone_Mapservice/MapServer/56", ("OBJECTID", "SSL"), geometry=True),
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
    # The same tax roll's billing history: each lot's tax levied in the nine prior tax years
    # (PY1 = last year; PY10 is nearly empty) and the current year's two halves. Lots retired
    # since then (subdivided, consolidated, condo conversions) are not on the roll.
    ArcGISLayer(
        "itspe_tax_history",
        "DCGIS_DATA/Property_and_Land_WebMercator/MapServer/53",
        ("OBJECTID", "SSL", "OLDTOTAL", "CY1YEAR", "CY1TAX", "CY2TAX",
         *(f"PY{i}{f}" for i in range(1, 10) for f in ("YEAR", "TAX"))),
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

# DOB building permits, one layer per issue year. These list issued permits only:
# no application date, and nothing for applications that were never issued.
# Owner and applicant names are left out of the fetch.
# Comparison cities (Philadelphia, New York, Boston) and Census 2020 place boundaries, for the
# designation comparison (analysis/comps.py). Each city's own layers; units differ by city.
CENSUS_PLACES = {"Washington": "1150000", "New York": "3651000", "Philadelphia": "4260000", "Boston": "2507000"}
COMP_LAYERS = (
    ArcGISLayer("comps_census_places", "tigerWMS_Census2020/MapServer/26",
                ("GEOID", "NAME", "AREALAND", "AREAWATER", "POP100"), geometry=True,
                where="GEOID IN ({})".format(",".join(f"'{g}'" for g in CENSUS_PLACES.values())),
                base="https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb"),
    ArcGISLayer("comps_phl_sites", "Historic_sites_PhilReg/FeatureServer/0", geometry=True,
                base="https://services.arcgis.com/fLeGjb7u4uXqeF9q/arcgis/rest/services"),
    ArcGISLayer("comps_phl_districts", "HistoricDistricts_Local/FeatureServer/0", geometry=True,
                base="https://services.arcgis.com/fLeGjb7u4uXqeF9q/arcgis/rest/services"),
    ArcGISLayer("comps_bos_landmarks", "ISD/landmarks_historic_districts_viewing/MapServer/0", geometry=True,
                base="https://gisportal.boston.gov/arcgis/rest/services"),
    ArcGISLayer("comps_bos_districts", "EnvironmentEnergy/OpenData/MapServer/4", geometry=True,
                base="https://gisportal.boston.gov/arcgis/rest/services"),
)
# Census areal hydrography around each city, simplified to about 20 m, for the animated maps' water.
CITY_EXTENTS = {"Washington": (-77.13, 38.78, -76.90, 39.01), "New York": (-74.27, 40.47, -73.69, 40.93),
                "Philadelphia": (-75.29, 39.86, -74.95, 40.15), "Boston": (-71.20, 42.22, -70.74, 42.41)}
WATER_LAYERS = tuple(
    ArcGISLayer(f"comps_water_{city.lower().replace(' ', '_')}", "Hydro/MapServer/1", ("OBJECTID", "NAME", "MTFCC"),
                geometry=True, envelope=box, simplify=0.0002,
                base="https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb")
    for city, box in CITY_EXTENTS.items())
# NYC Landmarks Preservation Commission layers on NYC Open Data (Socrata).
NYC_DATASETS = {"comps_nyc_landmarks": "buis-pvji", "comps_nyc_districts": "skyk-mpzq"}

# Official address data for counting buildings in each city (analysis/comps.py): one point per
# addressed building, deduplicated in normalize/comps.py. Points only, no names.
BUILDING_LAYERS = (
    ArcGISLayer("comps_dc_address_points", "DCGIS_DATA/Location_WebMercator/MapServer/0",
                ("OBJECTID", "MAR_ID", "RESIDENTIAL_TYPE"), geometry=True,
                where="STATUS = 'ACTIVE' AND BUILDING = 'Y'"),
    ArcGISLayer("comps_bos_sam_addresses", "SAM/Live_SAM_Address/MapServer/0",
                ("OBJECTID", "SAM_ADDRESS_ID", "BUILDING_ID"), geometry=True,
                base="https://gisportal.boston.gov/arcgis/rest/services"),
)
# NYC AddressPoint (each point carries its building's BIN): dataset id and the columns kept.
NYC_POINT_DATASETS = {"comps_nyc_address_points": ("uf93-f8nk", "addresspointid,bin,the_geom")}
# Philadelphia's property assessment points (OPA) on the city's Carto server; owner fields are not fetched.
PHL_CARTO = "https://phl.carto.com/api/v2/sql"
PHL_PROPERTIES_SQL = ("SELECT objectid, parcel_number, category_code_description, unit, "
                      "ST_X(the_geom) AS lon, ST_Y(the_geom) AS lat FROM opa_properties_public")

PERMIT_LAYER_IDS = {
    2009: 12, 2010: 11, 2011: 10, 2012: 7, 2013: 6, 2014: 5, 2015: 25, 2016: 24, 2017: 37,
    2018: 9, 2019: 8, 2020: 2, 2021: 3, 2022: 14, 2023: 15, 2024: 16, 2025: 17, 2026: 18,
}
PERMIT_SUBTYPES = ("RAZE", "DEMOLITION", "NEW BUILDING", "ADDITION")
PERMIT_LAYERS = tuple(
    ArcGISLayer(
        f"permits_{year}",
        f"FEEDS/DCRA/FeatureServer/{layer_id}",
        (
            "OBJECTID", "PERMIT_ID", "ISSUE_DATE", "PERMIT_TYPE_NAME", "PERMIT_SUBTYPE_NAME",
            "APPLICATION_STATUS_NAME", "FULL_ADDRESS", "DESC_OF_WORK", "SSL",
            "MARADDRESSREPOSITORYID", "LATITUDE", "LONGITUDE", "WARD",
        ),
        where="PERMIT_SUBTYPE_NAME IN ({})".format(",".join(f"'{s}'" for s in PERMIT_SUBTYPES)),
    )
    for year, layer_id in PERMIT_LAYER_IDS.items()
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
    *(Document(f"hpo_annual_report_fy{y}", f"{_OP_ATTACH}/{y}_HPO_Annual_Report.pdf")
      for y in (*range(1979, 1989), 1994, *range(1996, 2009))),
    # Found via planning.dc.gov/publication/<year>-hpo-annual-report (no FY1995, 2024 or 2025 page as of 2026-10-18).
    *(Document(f"hpo_annual_report_fy{y}", f"{_OP_ATTACH}/{y}%2520HPO%2520Annual%2520Report.pdf")
      for y in (1989, 1990, 1991, 1992, 1993)),
    Document("hpo_annual_report_fy2010", f"{_OP_ATTACH}/ANNUAL%2520REPORT%25202010.pdf"),
    Document("hpo_annual_report_fy2011", f"{_OP_ATTACH}/Annual%2520Report%2520FY%25202011%2520webvers.pdf"),
    Document("hpo_annual_report_fy2013", f"{_OP_ATTACH}/FY%202013%20Annual%20Report%20.pdf"),
    Document("hpo_annual_report_fy2014", f"{_OP_ATTACH}/FY14%20Annual%20Report-FINAL-July%2021-small.pdf"),
    Document("hpo_annual_report_fy2016", f"{_OP_ATTACH}/FY%202016%20Annual%20Report%20web%20version.pdf"),
    Document("hpo_annual_report_fy2019", f"{_OP_ATTACH}/Annual%20Report%202019-FINAL-small.pdf"),
    Document("hpo_annual_report_fy2023", f"{_OP_ATTACH}/DC%20Historic%20Preservation%20Office%202023%20Annual%20Report.pdf"),
    Document("hpo_annual_report_fy2009", f"{_OP_ATTACH}/2009%2520Annual%2520Report%2520Finall.pdf"),
    Document("hpo_annual_report_fy2012", f"{_OP_ATTACH}/FY%202012%20Annual%20Report.pdf"),
    Document("hpo_annual_report_fy2015", f"{_OP_ATTACH}/FY%202015%20Annual%20Report.pdf"),
    Document("hpo_annual_report_fy2017", f"{_OP_ATTACH}/2017%20Annual%20Report%20Final.pdf"),
    Document("hpo_annual_report_fy2018", f"{_OP_ATTACH}/2018%20Annual%20Report.pdf"),
    Document("hpo_annual_report_fy2020", f"{_OP_ATTACH}/Annual%20HPO%20Annual%20Report%20FY%202020.pdf"),
    Document("hpo_annual_report_fy2021", f"{_OP_ATTACH}/2021%20HPO%20Annual%20Report.pdf"),
    Document("hpo_annual_report_fy2022", f"{_OP_ATTACH}/2022%20Annual%20Report%20FINAL%20corrected.pdf"),
    Document("hp_plan_implementation_2025", f"{_OP_ATTACH}/2025%20HP%20Plan-FINAL%20%20Implementation%20Report.pdf"),
)
DOCUMENTS = (INVENTORY_2009, *INVENTORY_UPDATES, *HPO_REPORTS)


DCPL_EIN = "521038849"  # DC Preservation League


@dataclass(frozen=True)
class WebPage:
    key: str
    url: str
    follow_pdfs: bool = False


_DCPL = "https://dcpreservation.org"
WEB_PAGES = (
    WebPage("dcpl_nominations_and_landmarks", f"{_DCPL}/resources/nominations-and-landmarks/", True),
    WebPage("dcpl_past_issues", f"{_DCPL}/places-and-spaces/past-issues/", True),
    WebPage("dcpl_current_issues", f"{_DCPL}/places-and-spaces/current-issues/", True),
    WebPage("dcpl_endangered_places", f"{_DCPL}/endangered-places/", True),
    WebPage("dcpl_grants", f"{_DCPL}/grants/", True),
    WebPage("dcpl_history", f"{_DCPL}/about-us/history/"),
    WebPage("dcpl_board_of_trustees", f"{_DCPL}/about-us/board-of-trustees/"),
    WebPage("dcpl_staff", f"{_DCPL}/about-us/staff/"),
    WebPage("dcpl_news", f"{_DCPL}/about-us/news/"),
    WebPage("dcpl_inventory_2022_update", f"{_DCPL}/wp-content/uploads/2022/01/DC-Inventory-Landmarks-and-Historic-Districts_2022Update.pdf"),
    WebPage("hpo_pending_nominations", "https://planning.dc.gov/page/pending-nominations-dc-inventory", True),
    # DCPL grant award lists
    WebPage("dcpl_grants_2014_2016", f"{_DCPL}/wp-content/uploads/2021/10/2014-2016-Awarded-Projects-1.pdf"),
    WebPage("dcpl_grants_2018_2023", f"{_DCPL}/wp-content/uploads/2023/08/2018-2023-Awarded-Projects.pdf"),
)


def secret(name: str) -> str | None:
    """An API token from the environment or the gitignored .env file."""
    if os.environ.get(name):
        return os.environ[name]
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            key, _, value = line.partition("=")
            if key.strip() == name:
                return value.strip()
    return None


def snapshot_dir() -> Path:
    """The raw snapshot the build reads: $HP_SNAPSHOT, else the newest complete one."""
    if name := os.environ.get("HP_SNAPSHOT"):
        return RAW / name
    complete = sorted(p.parent for p in RAW.glob("*/SNAPSHOT_COMPLETE"))
    if not complete:
        raise FileNotFoundError(f"No complete snapshot under {RAW}; run `make fetch`.")
    return complete[-1]
