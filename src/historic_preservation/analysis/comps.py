"""DC against New York, Philadelphia and Boston: landmarks per capita and designated land area.

Areas are computed in an equal-area projection (EPSG:5070), clipped to each city's 2020 Census
place boundary, and divided by the Census land area (AREALAND). A designated area is the union
of a city's included district and landmark polygons, so overlaps count once. Designations that are
mainly parkland (inputs/comps_parkland.csv) are also reported excluded, since New York's scenic
landmarks (its parks) are not in its landmark layer. Building shares count a building as designated
when its point falls inside a designation, from each city's official address data (`official_*`)
and, as a cross-check, OpenStreetMap (`osm_*`). Landmark counts are
each city's own unit (see normalize/comps.py). The time series uses only dated designations.
"""

import json

import duckdb
import pandas as pd

from historic_preservation.config import ANALYSIS, CENSUS_PLACES, INPUTS, MANUAL, NORMALIZED

FIRST_YEAR = 1950
OSM_FILES = {"Washington": "district-of-columbia", "New York": "new-york", "Philadelphia": "pennsylvania",
             "Boston": "massachusetts"}
DC_TREND_START_YEAR = 1964


def connect() -> duckdb.DuckDBPyConnection:
    con = duckdb.connect()
    con.install_extension("spatial")
    con.load_extension("spatial")
    to_ea = "ST_Transform(ST_MakeValid(ST_GeomFromGeoJSON(geometry)), {crs}, 'EPSG:5070', always_xy := true)"
    con.execute(f"""CREATE TABLE d AS SELECT * EXCLUDE (geometry), {to_ea.format(crs='crs')} AS geom
                    FROM read_parquet('{NORMALIZED / 'comps.parquet'}') WHERE included AND geometry IS NOT NULL""")
    con.execute(f"""CREATE TABLE p AS SELECT * EXCLUDE (geometry), {to_ea.format(crs="'EPSG:4326'")} AS geom
                    FROM read_parquet('{NORMALIZED / 'comps_places.parquet'}')""")
    parks = pd.read_csv(INPUTS / "comps_parkland.csv")
    con.execute("ALTER TABLE d ADD COLUMN parkland BOOLEAN DEFAULT false")
    for r in parks.itertuples():
        hit = con.execute("UPDATE d SET parkland = true WHERE city = ? AND name = ? RETURNING 1", [r.city, r.name]).fetchall()
        if not hit:
            raise ValueError(f"comps_parkland.csv: no designation named {r.name!r} in {r.city}")
    city_of = {g: c for c, g in CENSUS_PLACES.items()}
    con.execute("ALTER TABLE p ADD COLUMN city VARCHAR")
    for g, c in city_of.items():
        con.execute("UPDATE p SET city = ? WHERE geoid = ?", [c, g])
    return con


def area(con, city: str, where: str) -> float:
    return con.execute(f"""
        SELECT ST_Area(ST_Intersection(ST_Union_Agg(d.geom), (SELECT geom FROM p WHERE city = $1)))
        FROM d WHERE city = $1 AND ST_GeometryType(geom) IN ('POLYGON', 'MULTIPOLYGON') AND {where}""",
                       [city]).fetchone()[0] or 0.0


def _points(source: str) -> dict[str, str] | None:
    """Per city, a SQL source of (lon, lat) building points; None if any city's file is missing.

    official: each city's address data, one point per addressed building (normalize/comps.py).
    osm: one point inside each OpenStreetMap building (fetch/osm.py)."""
    if source == "official":
        f = NORMALIZED / "comps_buildings.parquet"
        return {c: f"(SELECT lon, lat FROM read_parquet('{f}') WHERE city = '{c}')" for c in OSM_FILES} if f.exists() else None
    files = {c: MANUAL / "osm" / f"{s}.parquet" for c, s in OSM_FILES.items()}
    return {c: f"read_parquet('{f}')" for c, f in files.items()} if all(f.exists() for f in files.values()) else None


def building_years(con, source: str) -> pd.DataFrame | None:
    """Each building point in the four cities with the first year a designation covered it (all,
    and excluding parkland)."""
    points = _points(source)
    if points is None:
        return None
    con.execute("CREATE OR REPLACE TABLE b (city VARCHAR, id BIGINT, geom GEOMETRY)")
    for c, src in points.items():
        con.execute(f"""INSERT INTO b SELECT ?, row_number() OVER (),
                        ST_Transform(ST_Point(lon, lat), 'EPSG:4326', 'EPSG:5070', always_xy := true)
                        FROM {src}""", [c])
    # One city at a time: a city-equality join condition stops DuckDB from planning a spatial join.
    hits = pd.concat([con.execute("""
        SELECT b.city, b.id,
               min(coalesce(dd.year, 9999)) AS first_year,
               min(CASE WHEN NOT dd.parkland THEN coalesce(dd.year, 9999) END) AS first_year_np
        FROM (SELECT * FROM b WHERE city = $1) b
        JOIN (SELECT * FROM d WHERE city = $1) dd ON ST_Intersects(b.geom, dd.geom)
        GROUP BY ALL""", [c]).df() for c in points])
    allb = con.execute("SELECT city, id FROM b").df()
    return allb.merge(hits, on=["city", "id"], how="left")


def current(con) -> pd.DataFrame:
    rows = []
    for city, pop, land in con.execute("SELECT city, pop100, arealand FROM p ORDER BY city").fetchall():
        n = dict(con.execute("SELECT kind, count(DISTINCT feature_id) FROM d WHERE city = ? GROUP BY kind",
                             [city]).fetchall())
        rows.append({
            "city": city, "population_2020": int(pop), "land_area_km2": round(land / 1e6, 1),
            "landmarks": n.get("landmark", 0), "districts": n.get("district", 0),
            "landmarks_per_100k": round(n.get("landmark", 0) / pop * 1e5, 1),
            "district_area_share": area(con, city, "kind = 'district'") / land,
            "landmark_area_share": area(con, city, "kind = 'landmark'") / land,
            "designated_area_share": area(con, city, "TRUE") / land,
            "designated_area_share_excl_parkland": area(con, city, "NOT parkland") / land,
        })
    return pd.DataFrame(rows)


def by_year(con) -> pd.DataFrame:
    last = pd.Timestamp.today().year
    out = []
    for city, land in con.execute("SELECT city, arealand FROM p").fetchall():
        years = {y for (y,) in con.execute("SELECT DISTINCT year FROM d WHERE city = ? AND year IS NOT NULL",
                                           [city]).fetchall()}
        share = 0.0
        for y in range(FIRST_YEAR, last + 1):
            if y in years or y == FIRST_YEAR:
                share = area(con, city, f"year <= {y}") / land
                share_np = area(con, city, f"year <= {y} AND NOT parkland") / land
            n = con.execute("""SELECT count(DISTINCT feature_id) FROM d
                               WHERE city = ? AND kind = 'landmark' AND year <= ?""", [city, y]).fetchone()[0]
            out.append({"city": city, "year": y, "landmarks": n, "designated_area_share": share,
                        "designated_area_share_excl_parkland": share_np})
    return pd.DataFrame(out)


def dc_designated_share_trend(years: pd.DataFrame, start_year: int = DC_TREND_START_YEAR) -> dict:
    """OLS trend in DC's non-park designated land share, in percentage points per year.

    The 100-percent year is only a straight-line extrapolation of the historical trend. It is
    reported to reproduce the post's rhetorical calculation, not as a forecast.
    """
    d = years[(years["city"] == "Washington") & (years["year"] >= start_year)].copy()
    x = d["year"].astype(float)
    y = d["designated_area_share_excl_parkland"].astype(float) * 100
    x_centered = x - x.mean()
    slope = (x_centered * (y - y.mean())).sum() / x_centered.pow(2).sum()
    intercept = y.mean() - slope * x.mean()
    fitted = intercept + slope * x
    r_squared = 1 - (y - fitted).pow(2).sum() / (y - y.mean()).pow(2).sum()
    return {
        "city": "Washington",
        "metric": "designated_area_share_excl_parkland",
        "start_year": start_year,
        "end_year": int(d["year"].max()),
        "observations": int(len(d)),
        "slope_percentage_points_per_year": float(slope),
        "intercept_percentage_points": float(intercept),
        "r_squared": float(r_squared),
        "linear_extrapolation_year_at_100_percent": float((100 - intercept) / slope),
        "extrapolation_is_forecast": False,
    }


def run() -> None:
    if not (NORMALIZED / "comps.parquet").exists():
        return
    con = connect()
    cur = current(con)
    years = by_year(con)
    for source in ("official", "osm"):
        bld = building_years(con, source)
        if bld is None:
            continue
        # 9999 marks buildings covered only by undated designations: designated today, not in the time series.
        g = bld.groupby("city")
        cur[f"{source}_buildings"] = cur["city"].map(g.size())
        cur[f"{source}_buildings_designated_share"] = cur["city"].map(g["first_year"].apply(lambda s: s.notna().mean()))
        cur[f"{source}_buildings_designated_share_excl_parkland"] = cur["city"].map(
            g["first_year_np"].apply(lambda s: s.notna().mean()))
        n = years["city"].map(g.size())
        years[f"{source}_buildings_designated_share_excl_parkland"] = [
            (bld.loc[bld["city"] == c, "first_year_np"] <= y).sum() for c, y in zip(years["city"], years["year"])] / n
    cur.to_csv(ANALYSIS / "comps_current.csv", index=False)
    years.to_csv(ANALYSIS / "comps_by_year.csv", index=False)
    (ANALYSIS / "dc_designated_share_trend.json").write_text(
        json.dumps(dc_designated_share_trend(years), indent=1)
    )
    c = pd.read_parquet(NORMALIZED / "comps.parquet", columns=["city", "kind", "included", "excluded_why",
                                                               "feature_id", "year"])
    inc = c[c["included"]].drop_duplicates("feature_id")
    summary = {
        "excluded": c[~c["included"]].drop_duplicates("feature_id").groupby(["city", "excluded_why"]).size()
                     .reset_index(name="n").to_dict("records"),
        "undated_included": inc[inc["year"].isna()].groupby(["city", "kind"]).size().reset_index(name="n")
                             .to_dict("records"),
        "units": {
            "Washington": "DC Inventory landmark features (GIS), designated or with a designation date",
            "New York": "LPC individual landmark sites (interior and scenic landmarks are not in this layer)",
            "Philadelphia": "parcels individually listed on the Philadelphia Register (rowhouses count one each)",
            "Boston": "approved Boston Landmarks (petitions)",
        },
        "official_building_units": {
            "Washington": "active MAR address points flagged as buildings, one per location",
            "New York": "AddressPoint, one per building identification number (BIN)",
            "Philadelphia": "OPA property points other than vacant land, one per location (condo units collapse)",
            "Boston": "SAM addresses, one per BUILDING_ID",
        },
    }
    (ANALYSIS / "comps_summary.json").write_text(json.dumps(summary, indent=1, default=str))
