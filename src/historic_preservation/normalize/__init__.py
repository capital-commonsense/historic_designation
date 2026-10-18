"""Normalize stage: raw ArcGIS pages -> typed tables in data/normalized/.

Owner names stay in the raw snapshot; nothing here writes them out.
"""

import json

import pandas as pd

from historic_preservation.config import (
    HPO_REPORTS,
    INVENTORY_2009,
    MANUAL,
    INVENTORY_UPDATES,
    NORMALIZED,
    snapshot_dir,
)
from historic_preservation.fetch.arcgis import read_features
from historic_preservation.fetch.documents import document_path
from historic_preservation.normalize.inventory import extract_dates, parse_entries
from historic_preservation.normalize.inventory_updates import parse_items
from historic_preservation.normalize.hpo_tables import extract_all as hpo_table_rows
from historic_preservation.normalize import dcpl_grants
from historic_preservation.normalize import hprb as hprb_records
from historic_preservation.normalize import dcoz as dcoz_records
from historic_preservation.normalize import courts
from historic_preservation.normalize import mayors_agent
from historic_preservation.normalize import permits as permit_records

ITSPE_DROP = ("OWNERNAME", "OWNNAME2")


def norm_ssl(s: pd.Series) -> pd.Series:
    """Collapse whitespace runs so 'SQUARE    LOT' variants compare equal."""
    return s.str.strip().str.replace(r"\s+", " ", regex=True).replace("", pd.NA)


def split_names(s: pd.Series) -> pd.Series:
    """Clean a ';'-joined name list: strip each part, drop empties, keep order."""
    def clean(v):
        if not isinstance(v, str):
            return pd.NA
        parts = [p.strip() for p in v.split(";") if p.strip()]
        return ";".join(parts) if parts else pd.NA

    return s.map(clean).astype("string")


def epoch_ms_to_date(s: pd.Series) -> pd.Series:
    return pd.to_datetime(s, unit="ms", errors="coerce").dt.date


def attributes(snapshot, key: str) -> pd.DataFrame:
    return pd.DataFrame([f["attributes"] for f in read_features(snapshot, key)])


def zoning_lookup(snapshot) -> pd.DataFrame:
    df = attributes(snapshot, "zoning_lookup")
    out = pd.DataFrame(
        {
            "objectid": df["OBJECTID"],
            "ssl": norm_ssl(df["SSL"].astype("string")),
            "square": df["SQUARE"].str.strip(),
            "suffix": df["SUFFIX"].str.strip(),
            "lot": df["LOT"].str.strip(),
            "address": df["PREMISEADD"].str.strip(),
            "ward": df["WARD_ID"].astype("string"),
            "anc": df["ANC_ID"].astype("string"),
            "zoning": df["ZONING"].astype("string"),
            "zone_district": df["ZONE_DISTRICT"].astype("string"),
            "zoning_1958": df["ZR58"].astype("string"),
            "overlay": df["OVERLAY_SHORT"].astype("string"),
            "historic_districts": split_names(df["HISTORICDISTRICT_NAME"]),
            "landmark_label": split_names(df["HISTORICLANDMARK_LABEL"]),
        }
    )
    out["in_district"] = out["historic_districts"].notna()
    out["is_landmark"] = out["landmark_label"].notna()
    out["designated"] = out["in_district"] | out["is_landmark"]
    return out


def itspe(snapshot) -> pd.DataFrame:
    df = attributes(snapshot, "itspe").drop(columns=list(ITSPE_DROP))
    df.columns = df.columns.str.lower()
    for col in ("ssl", "pressl", "piparentlot"):
        df[col] = norm_ssl(df[col].astype("string"))
    for col in ("square", "suffix", "lot", "proptype", "usecode", "classtype", "nbhdname", "unitnumber"):
        df[col] = df[col].astype("string").str.strip()
    df["ward"] = df.pop("prms_ward").astype("string").str.strip()
    for col in ("saledate", "deeddate", "extractdat"):
        df[col] = epoch_ms_to_date(df[col])
    # Inferred flags. zero_tax approximates exempt property (federal, District,
    # institutional) but also catches fully abated taxable property.
    df["is_condo"] = df["proptype"].str.contains("Condo", na=False)
    df["zero_tax"] = df["annualtax"].fillna(0) == 0
    return df


def condo_relate(snapshot) -> pd.DataFrame:
    df = attributes(snapshot, "condo_relate")
    return pd.DataFrame(
        {
            "unit_ssl": norm_ssl(df["SSL"].astype("string")),
            "lot_ssl": norm_ssl(df["MAT_SSL"].astype("string")),
            "regime": df["REGIME"].astype("string"),
            "regime_id": df["REGIME_ID"],
            "condo_name": df["NAME"].astype("string").str.strip(),
        }
    )


def gis_layer(snapshot, key: str) -> pd.DataFrame:
    df = attributes(snapshot, key)
    df.columns = df.columns.str.lower()
    for col in [c for c in df.columns if "date" in c]:
        df[col] = epoch_ms_to_date(df[col])
    for col in df.select_dtypes("object"):
        if df[col].map(lambda v: isinstance(v, str)).any():
            df[col] = df[col].astype("string").str.strip()
    return df


def inventory_2009(snapshot) -> pd.DataFrame:
    path = document_path(snapshot, INVENTORY_2009)
    entries, _ = parse_entries(path)
    return pd.DataFrame(
        [{"name": e.name, "page": e.page, **extract_dates(e.text), "text": e.text} for e in entries]
    )


def inventory_updates(snapshot) -> pd.DataFrame:
    rows = []
    for doc in (*INVENTORY_UPDATES, *(d for d in HPO_REPORTS if d.key in ("hpo_annual_report_fy2021", "hpo_annual_report_fy2022"))):
        path = document_path(snapshot, doc)
        if not path.exists():
            continue
        for item in parse_items(path):
            rows.append({"source_doc": doc.key, **item.fields()})
    return pd.DataFrame(rows)


DCPL_990_FIELDS = {
    "tax_prd": "tax_period",  # YYYYMM of fiscal year end
    "formtype": "form_type",  # 0 = 990, 1 = 990-EZ, 2 = 990-PF
    "totrevenue": "total_revenue",
    "totcntrbgfts": "contributions_grants",
    "totprgmrevnue": "program_service_revenue",
    "invstmntinc": "investment_income",
    "totfuncexpns": "total_expenses",
    "compnsatncurrofcr": "officer_compensation",
    "othrsalwages": "other_salaries_wages",
    "totassetsend": "total_assets_end",
    "totliabend": "total_liabilities_end",
    "totnetassetend": "net_assets_end",
}


def dcpl_990_summary(snapshot) -> pd.DataFrame:
    """ProPublica's extracted 990 fields (filings with data only; FY2011+)."""
    org = json.loads((snapshot / "dcpl_990" / "organization.json").read_text())
    df = pd.DataFrame(org["filings_with_data"])[list(DCPL_990_FIELDS)].rename(columns=DCPL_990_FIELDS)
    df["fiscal_year_end"] = pd.to_datetime(df["tax_period"].astype(str), format="%Y%m").dt.to_period("M")
    others = pd.DataFrame(org["filings_without_data"])[["tax_prd", "formtype_str"]]
    others.columns = ["tax_period", "form_type_str"]
    return pd.concat([df, others], ignore_index=True).sort_values("tax_period").reset_index(drop=True)


GEO_LAYERS = ("lot_polygons", "historic_districts", "landmark_points", "landmark_polygons",
              "potential_landmarks", "preservation_easements")


def geo_layer(snapshot, key: str) -> pd.DataFrame:
    """Attributes (lowercased) plus the geometry as a GeoJSON string in EPSG:4326."""
    feats = read_features(snapshot, key)
    df = pd.DataFrame([f["attributes"] for f in feats])
    df.columns = df.columns.str.lower()
    df["geometry"] = [json.dumps(f["geometry"]) if f["geometry"] else None for f in feats]
    if "ssl" in df:
        df["ssl"] = norm_ssl(df["ssl"].astype("string"))
    return df


def run() -> None:
    snapshot = snapshot_dir()
    print(f"normalize: reading {snapshot}")
    NORMALIZED.mkdir(parents=True, exist_ok=True)
    zoning_lookup(snapshot).to_parquet(NORMALIZED / "zoning_lookup.parquet", index=False)
    itspe(snapshot).to_parquet(NORMALIZED / "itspe.parquet", index=False)
    condo_relate(snapshot).to_parquet(NORMALIZED / "condo_relate.parquet", index=False)
    for key in ("condo_one_to_many", "historic_districts", "landmark_points", "landmark_polygons",
                "potential_landmarks", "preservation_easements"):
        gis_layer(snapshot, key).to_csv(NORMALIZED / f"{key}.csv", index=False)
    (NORMALIZED / "geo").mkdir(exist_ok=True)
    for key in GEO_LAYERS:
        geo_layer(snapshot, key).to_parquet(NORMALIZED / "geo" / f"{key}.parquet", index=False)
    permit_records.permits(snapshot).to_csv(NORMALIZED / "permits.csv", index=False)
    if (snapshot / "dcpl_990" / "organization.json").exists():
        dcpl_990_summary(snapshot).to_csv(NORMALIZED / "dcpl_990_summary.csv", index=False)
    if (snapshot / "hprb" / "index.json").exists():
        hprb_records.extract(snapshot / "hprb").to_csv(NORMALIZED / "hprb_designation_actions.csv", index=False)
    if (snapshot / "dcoz" / "index.json").exists():
        dcoz_records.exhibits(snapshot / "dcoz").to_csv(NORMALIZED / "zc_exhibits.csv", index=False)
    if (snapshot / "court_opinions" / "manifest.json").exists():
        courts.opinions(snapshot / "court_opinions").to_csv(NORMALIZED / "court_opinions.csv", index=False)
        courts.cases(snapshot / "court_opinions").to_csv(NORMALIZED / "court_cases.csv", index=False, date_format="%Y-%m-%d")
    if (MANUAL / "mayors_agent" / "mayors_agent_catalog.json").exists():
        mayors_agent.decisions(MANUAL / "mayors_agent").to_csv(
            NORMALIZED / "mayors_agent_decisions.csv", index=False, date_format="%Y-%m-%d")
    if (snapshot / "web" / "hpo_pending_nominations.html").exists():
        hpo_pending_nominations(snapshot).to_csv(NORMALIZED / "hpo_pending_nominations.csv", index=False)
    if (snapshot / "web" / "dcpl_nominations_and_landmarks.html").exists():
        dcpl_pending_nominations(snapshot).to_csv(NORMALIZED / "dcpl_pending_nominations.csv", index=False)
    inventory_2009(snapshot).to_csv(NORMALIZED / "inventory_2009_entries.csv", index=False)
    inventory_updates(snapshot).to_csv(NORMALIZED / "inventory_update_items.csv", index=False)
    reports = {d.key: document_path(snapshot, d) for d in (*INVENTORY_UPDATES, *HPO_REPORTS)}
    # Hand-fetched reports (records_request/manual_fetch.md item 5) fill gaps; fetched copies win.
    for pdf in sorted((MANUAL / "hpo_reports").glob("hpo_annual_report_fy*.pdf")):
        reports.setdefault(pdf.stem, pdf)
    hpo_table_rows(reports).to_csv(NORMALIZED / "hpo_landmark_table_rows.csv", index=False)
    web = snapshot / "web"
    grant_pdfs = [web / f"{k}.pdf" for k in ("dcpl_grants_2014_2016", "dcpl_grants_2018_2023")]
    if all(p.exists() for p in grant_pdfs):
        pd.concat([dcpl_grants.parse(p, p.stem) for p in grant_pdfs]).to_csv(
            NORMALIZED / "dcpl_grant_awards.csv", index=False)
    (NORMALIZED / "SNAPSHOT.json").write_text(json.dumps({"snapshot": snapshot.name}))


def dcpl_pending_nominations(snapshot) -> pd.DataFrame:
    """DCPL's own list of its pending nominations (as posted on its site; may be stale)."""
    path = snapshot / "web" / "dcpl_nominations_and_landmarks.html"
    import html as htmllib
    import re
    t = path.read_text(errors="ignore")
    t = re.sub(r"<(script|style).*?</\1>", "", t[t.find("<body"):], flags=re.S)
    m = re.search(r"Pending DCPL Nominations.*?(?=For a full list)", t, re.S)
    if not m:
        return pd.DataFrame(columns=["name", "address"])
    rows = []
    for li in re.findall(r"<li[^>]*>(.*?)</li>", m.group(0), re.S):
        it = htmllib.unescape(re.sub(r"<[^>]+>", "", li)).strip()
        if not it:
            continue
        link = re.search(r'href="([^"]+)"', li)
        posted = re.search(r"/uploads/(\d{4})/(\d{2})/", link.group(1)) if link else None
        name, _, address = it.rpartition(", ") if re.search(r",\s*\d", it) else (it, "", "")
        if address and not re.match(r"\d", address):  # e.g. "Lansburgh Park, Delaware Avenue between ..."
            name, address = it.split(", ", 1)
        rows.append({
            "name": name.strip(), "address": address.strip(),
            "nomination_pdf": link.group(1) if link else "",
            # upload month of the posted nomination PDF: a proxy for filing date, not the filing date
            "posted_month_proxy": f"{posted.group(1)}-{posted.group(2)}" if posted else "",
            "source": "dcpl_nominations_and_landmarks.html",
        })
    return pd.DataFrame(rows)


def hpo_pending_nominations(snapshot) -> pd.DataFrame:
    """HPO's list of pending nominations (case number, name, address, landmark vs district)."""
    import re
    from historic_preservation.normalize.hprb import html_text
    text = html_text(snapshot / "web" / "hpo_pending_nominations.html")
    rows, kind = [], None
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("Pending Historic Landmark"):
            kind = "landmark"
        elif line.startswith("Pending Historic District"):
            kind = "district"
        m = re.match(r"^(\d{2}-\d{2})\s+(.+)$", line)
        if kind and m:
            name, _, address = m.group(2).partition(" - ")
            rows.append({"case_no": m.group(1), "name": name.strip(), "address": address.strip(),
                         "list": kind, "case_year": 2000 + int(m.group(1)[:2]),
                         "source": "hpo_pending_nominations.html"})
    return pd.DataFrame(rows)
