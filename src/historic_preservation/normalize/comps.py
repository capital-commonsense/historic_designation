"""Designations in DC and three comparison cities, in one table (data/normalized/comps.parquet).

One row per designation feature: city, kind (landmark or district), name, designation date,
whether it counts as designated today (`included`, with `excluded_why` otherwise), and its
geometry as GeoJSON in the coordinate system named in `crs`. Units are each city's own: New York landmark sites,
Philadelphia registered parcels, Boston landmark petitions, DC Inventory landmark features.
"""

import json
from datetime import date

import pandas as pd

from historic_preservation.config import INPUTS, NORMALIZED
from historic_preservation.fetch.arcgis import read_features

TODAY = pd.Timestamp(date.today())


def _arcgis(snapshot, key: str) -> pd.DataFrame:
    feats = read_features(snapshot, key)
    df = pd.DataFrame([f["attributes"] for f in feats])
    df["geometry"] = [json.dumps(f["geometry"]) if f["geometry"] else None for f in feats]
    return df


def _socrata(snapshot, key: str) -> pd.DataFrame:
    feats = json.loads((snapshot / "socrata" / key / "data.geojson").read_text())["features"]
    df = pd.DataFrame([f["properties"] for f in feats])
    df["geometry"] = [json.dumps(f["geometry"]) if f["geometry"] else None for f in feats]
    return df


def _ms(s: pd.Series) -> pd.Series:
    return pd.to_datetime(s, unit="ms", errors="coerce")


def rows(city, kind, name, designated, geometry, included=True, why="", feature_id=None, crs="EPSG:4326") -> pd.DataFrame:
    """feature_id groups the parts of one designation (DC landmarks with several polygons); counts use it."""
    df = pd.DataFrame({"city": city, "kind": kind, "name": name, "designated": pd.to_datetime(designated),
                       "included": included, "excluded_why": why, "geometry": geometry, "crs": crs})
    df["feature_id"] = (f"{city}/{kind}/" + pd.Series(range(len(df)), index=df.index).astype(str)
                        if feature_id is None else feature_id)
    return df


def nyc(snapshot) -> list[pd.DataFrame]:
    lm = _socrata(snapshot, "comps_nyc_landmarks")
    d = _socrata(snapshot, "comps_nyc_districts")
    current = d["status_of_"].eq("DESIGNATED") & d["current_"].eq("Yes")
    # NYC Open Data serves these layers' GeoJSON in New York State Plane (feet), not WGS84.
    return [rows("New York", "landmark", lm["lpc_name"], pd.to_datetime(lm["desdate"], format="mixed", errors="coerce"),
                 lm["geometry"], crs="EPSG:2263"),
            rows("New York", "district", d["area_name"] + d["extension"].eq("Yes").map({True: " (extension)", False: ""}),
                 pd.to_datetime(d["desdate"], format="mixed", errors="coerce"), d["geometry"], current,
                 (~current).map({True: "not a current designation", False: ""}), crs="EPSG:2263")]


def philadelphia(snapshot) -> list[pd.DataFrame]:
    s = _arcgis(snapshot, "comps_phl_sites")
    indiv = s[s["idesigdate1"].notna()]
    d = _arcgis(snapshot, "comps_phl_districts")
    # 'designated' holds 3000-01-01 for some districts; the text copy sometimes has the real date
    # (Powelton Village, 11/10/2022). A date in the future, or none, marks a pending or undated district.
    text = pd.to_datetime(d["designated1"], format="%m/%d/%Y", errors="coerce")
    when = _ms(d["designated"]).where(lambda x: x <= TODAY, text.where(text <= TODAY))
    iwhen = _ms(indiv["idesigdate1"])
    ipending = iwhen > TODAY
    return [rows("Philadelphia", "landmark", indiv["loc"], iwhen.where(~ipending), indiv["geometry"], ~ipending,
                 ipending.map({True: "designation date 3000-01-01 (pending placeholder)", False: ""})),
            rows("Philadelphia", "district", d["name"], when, d["geometry"], when.notna(),
                 when.isna().map({True: "no designation date (pending or not recorded)", False: ""}))]


def boston(snapshot) -> list[pd.DataFrame]:
    lm = _arcgis(snapshot, "comps_bos_landmarks")
    d = _arcgis(snapshot, "comps_bos_districts")
    approved = lm["Status"].eq("Approved Landmark")
    district = d["YEAR"].notna() & ~d["TYPE"].str.contains("Protection|PA", na=False)
    return [rows("Boston", "landmark", lm["Common_Name"], _ms(lm["Date_Designated_1"]), lm["geometry"], approved,
                 (~approved).map({True: "pending landmark petition", False: ""})),
            rows("Boston", "district", d["HIST_NAME"], pd.to_datetime(d["YEAR"].astype("Int64").astype(str) + "-07-01",
                                                                       errors="coerce"),
                 d["geometry"], district, (~district).map({True: "protection area (no designation year)", False: ""}))]


def dc(snapshot) -> list[pd.DataFrame]:
    from historic_preservation.analysis.eras import district_first_dates

    dates = pd.read_csv(INPUTS / "landmark_dates.csv", parse_dates=["first_date"]).set_index("uniqueid")
    pts = _arcgis(snapshot, "landmark_points")
    polys = _arcgis(snapshot, "landmark_polygons")
    # Each landmark's polygon parts where it has them, else its point.
    lm = pd.concat([polys[["UNIQUEID", "geometry"]],
                    pts.loc[~pts["UNIQUEID"].isin(polys["UNIQUEID"]), ["UNIQUEID", "geometry"]]], ignore_index=True)
    meta = pts.drop_duplicates("UNIQUEID").set_index("UNIQUEID")
    meta = pd.concat([meta, polys.drop_duplicates("UNIQUEID").set_index("UNIQUEID").loc[lambda x: ~x.index.isin(meta.index)]])
    lm["NAME"] = lm["UNIQUEID"].map(meta["NAME"])
    lm["STATUS"] = lm["UNIQUEID"].map(meta["STATUS"])
    hd = _arcgis(snapshot, "historic_districts")
    hd["NAME"] = hd["NAME"].str.strip()
    first = district_first_dates().set_index("district")["first_date"]
    when = lm["UNIQUEID"].map(dates["first_date"])
    # GIS STATUS 'Pending' is stale for many landmarks; a reviewed designation date also counts.
    ok = lm["STATUS"].eq("Designated") | when.notna()
    return [rows("Washington", "landmark", lm["NAME"], when, lm["geometry"], ok,
                 (~ok).map({True: "GIS status Pending and no designation date found", False: ""}),
                 "Washington/landmark/" + lm["UNIQUEID"]),
            rows("Washington", "district", hd["NAME"], hd["NAME"].map(first), hd["geometry"])]


def comps(snapshot) -> pd.DataFrame:
    if not (snapshot / "socrata" / "comps_nyc_landmarks" / "COMPLETE.json").exists():
        return pd.DataFrame()
    df = pd.concat([*dc(snapshot), *nyc(snapshot), *philadelphia(snapshot), *boston(snapshot)], ignore_index=True)
    df["year"] = df["designated"].dt.year.astype("Int64")
    return df


def places(snapshot) -> pd.DataFrame:
    df = _arcgis(snapshot, "comps_census_places")
    return df.rename(columns=str.lower)[["geoid", "name", "arealand", "areawater", "pop100", "geometry"]]


def _points(features, **props) -> pd.DataFrame:
    """Point features as lon/lat plus the named properties (renamed to the keyword)."""
    return pd.DataFrame({"lon": [f["geometry"]["coordinates"][0] if f["geometry"] else None for f in features],
                         "lat": [f["geometry"]["coordinates"][1] if f["geometry"] else None for f in features],
                         **{k: [f["properties" if "properties" in f else "attributes"][v] for f in features]
                            for k, v in props.items()}})


def buildings(snapshot) -> pd.DataFrame:
    """One point per addressed building in each city, from its official address data.

    DC: active MAR address points flagged as buildings, one per location. New York: AddressPoint,
    one per BIN (placeholder BINs n000000 dropped). Boston: SAM addresses, one per BUILDING_ID.
    Philadelphia: OPA property points other than vacant land, one per location (condominium
    units share their building's point). Units are close but not identical: see analysis/comps.py.
    """
    if not (snapshot / "carto" / "comps_phl_properties" / "COMPLETE.json").exists():
        return pd.DataFrame()
    dc_ = _points(read_features(snapshot, "comps_dc_address_points"), id="MAR_ID")
    dc_ = dc_.round({"lon": 6, "lat": 6}).drop_duplicates(["lon", "lat"])
    nyc_ = _points([f for p in sorted((snapshot / "socrata" / "comps_nyc_address_points").glob("page_*.geojson"))
                    for f in json.loads(p.read_text())["features"]], id="bin")
    nyc_ = nyc_[nyc_["id"].notna() & ~nyc_["id"].astype(str).str.fullmatch(r"\d000000")].drop_duplicates("id")
    bos = _points(read_features(snapshot, "comps_bos_sam_addresses"), id="BUILDING_ID").drop_duplicates("id")
    phl = pd.concat([pd.read_csv(p, dtype={"parcel_number": str}) for p in
                     sorted((snapshot / "carto" / "comps_phl_properties").glob("ids_*.csv"))])
    phl = phl[~phl["category_code_description"].fillna("").str.startswith("VACANT")]
    phl = phl.rename(columns={"parcel_number": "id"}).round({"lon": 6, "lat": 6}).drop_duplicates(["lon", "lat"])
    out = pd.concat([d.assign(city=c)[["city", "id", "lon", "lat"]] for c, d in
                     (("Washington", dc_), ("New York", nyc_), ("Boston", bos), ("Philadelphia", phl))])
    out = out.dropna(subset=["lon", "lat"])
    out["id"] = out["id"].astype(str)
    return out.reset_index(drop=True)
