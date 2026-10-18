"""Normalize stage: raw ArcGIS pages -> typed tables in data/normalized/.

Owner names stay in the raw snapshot; nothing here writes them out.
"""

import json

import pandas as pd

from historic_preservation.config import NORMALIZED, snapshot_dir
from historic_preservation.fetch.arcgis import read_features

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
    (NORMALIZED / "SNAPSHOT.json").write_text(json.dumps({"snapshot": snapshot.name}))
