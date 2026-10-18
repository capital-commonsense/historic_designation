"""Spatial joins in DuckDB: which lots each landmark and district covers.

A lot belongs to a polygon when at least half its area lies inside it (so
polygons that merely touch a neighbouring lot don't claim it). A landmark
point belongs to the lot that contains it. Areas are compared in EPSG:4326
degrees, which is fine for a ratio at DC's latitude.
"""

import duckdb

from historic_preservation.config import JOINED, NORMALIZED

GEO = NORMALIZED / "geo"
MIN_LOT_SHARE = 0.5


def connect() -> duckdb.DuckDBPyConnection:
    con = duckdb.connect()
    con.install_extension("spatial")
    con.load_extension("spatial")
    for key in ("lot_polygons", "historic_districts", "landmark_points", "landmark_polygons"):
        con.execute(f"""
            CREATE TABLE {key} AS
            SELECT * EXCLUDE (geometry), ST_MakeValid(ST_GeomFromGeoJSON(geometry)) AS geom
            FROM read_parquet('{GEO / key}.parquet') WHERE geometry IS NOT NULL
        """)
    con.execute("CREATE INDEX lot_idx ON lot_polygons USING RTREE (geom)")
    return con


def polygon_lots(con, table: str, id_col: str) -> duckdb.DuckDBPyRelation:
    return con.sql(f"""
        SELECT p.{id_col} AS feature_id, l.ssl, l.objectid AS lot_objectid,
               ST_Area(ST_Intersection(p.geom, l.geom)) / NULLIF(ST_Area(l.geom), 0) AS lot_share
        FROM {table} p JOIN lot_polygons l ON ST_Intersects(p.geom, l.geom)
        WHERE ST_Area(ST_Intersection(p.geom, l.geom)) / NULLIF(ST_Area(l.geom), 0) >= {MIN_LOT_SHARE}
    """)


def run() -> None:
    con = connect()
    landmark_polys = polygon_lots(con, "landmark_polygons", "uniqueid").select("*, 'polygon' AS method")
    landmark_points = con.sql("""
        SELECT p.uniqueid AS feature_id, l.ssl, l.objectid AS lot_objectid, 1.0 AS lot_share, 'point' AS method
        FROM landmark_points p JOIN lot_polygons l ON ST_Within(p.geom, l.geom)
    """)
    landmark_polys.union(landmark_points).order("feature_id, ssl").write_parquet(str(JOINED / "landmark_lots.parquet"))
    polygon_lots(con, "historic_districts", "name").order("feature_id, ssl").write_parquet(
        str(JOINED / "district_lots.parquet")
    )
