"""Join stage: attach the Zoning Lookup's lot-level historic status to every ITSPE record.

Match order:
  1. ITSPE SSL == lot SSL                       -> match_method "ssl"
  2. ITSPE PRESSL (a condo unit's underlying lot) -> "pressl"
  3. CONDORELATE unit SSL -> MAT_SSL lot           -> "condo_relate"
  4. majority status of the lot's square+suffix   -> "square_majority" (inferred)
  5. otherwise                                    -> "none" (treated as not designated)

Methods 1-3 are exact lot matches ("strict"); 4 is an approximation.
"""

import pandas as pd

from historic_preservation.config import JOINED, NORMALIZED

STATUS = ["designated", "in_district", "is_landmark", "historic_districts", "landmark_label", "ward"]


def square_key(df: pd.DataFrame) -> pd.Series:
    return df["square"].fillna("") + "|" + df["suffix"].fillna("")


def square_majority(zl: pd.DataFrame) -> pd.DataFrame:
    """Per square+suffix: majority flags and the most common district name."""
    g = zl.assign(sq=square_key(zl)).groupby("sq")
    out = g[["designated", "in_district", "is_landmark"]].mean().rename(columns=lambda c: f"{c}_share")
    for flag in ("designated", "in_district", "is_landmark"):
        out[flag] = out[f"{flag}_share"] > 0.5
    out["historic_districts"] = g["historic_districts"].agg(
        lambda s: s.mode().iloc[0] if s.notna().any() else pd.NA
    )
    out["landmark_label"] = pd.NA
    out["ward"] = g["ward"].agg(lambda s: s.mode().iloc[0] if s.notna().any() else pd.NA)
    out["historic_districts"] = out["historic_districts"].where(out["in_district"])
    return out


STRICT_METHODS = ("ssl", "pressl", "condo_relate")


def join_status(itspe: pd.DataFrame, zl: pd.DataFrame, condos: pd.DataFrame) -> pd.DataFrame:
    lots = zl.dropna(subset=["ssl"]).drop_duplicates("ssl").set_index("ssl")[STATUS]
    squares = square_majority(zl)
    unit_to_lot = condos.dropna(subset=["unit_ssl"]).drop_duplicates("unit_ssl").set_index("unit_ssl")["lot_ssl"]

    by_ssl = lots.reindex(itspe["ssl"]).set_axis(itspe.index)
    by_pressl = lots.reindex(itspe["pressl"]).set_axis(itspe.index)
    by_condo = lots.reindex(unit_to_lot.reindex(itspe["ssl"])).set_axis(itspe.index)
    by_square = squares.reindex(square_key(itspe)).set_axis(itspe.index)

    method = pd.Series("none", index=itspe.index)
    method[by_square["designated"].notna()] = "square_majority"
    method[by_condo["designated"].notna()] = "condo_relate"
    method[by_pressl["designated"].notna()] = "pressl"
    method[by_ssl["designated"].notna()] = "ssl"

    status = by_ssl[STATUS].copy()
    for name, src in (("pressl", by_pressl), ("condo_relate", by_condo), ("square_majority", by_square)):
        m = method == name
        status.loc[m, STATUS] = src.loc[m, STATUS]
    for flag in ("designated", "in_district", "is_landmark"):
        status[flag] = status[flag].astype("boolean").fillna(False).astype(bool)

    out = itspe.copy()
    out["match_method"] = method
    out["status_inferred"] = method == "square_majority"
    out["square_designated_share"] = by_square["designated_share"]
    out[[f"zl_{c}" if c == "ward" else c for c in STATUS]] = status[STATUS]
    return out


def run() -> None:
    JOINED.mkdir(parents=True, exist_ok=True)
    zl = pd.read_parquet(NORMALIZED / "zoning_lookup.parquet")
    itspe = pd.read_parquet(NORMALIZED / "itspe.parquet")
    condos = pd.read_parquet(NORMALIZED / "condo_relate.parquet")
    joined = join_status(itspe, zl, condos)
    joined.to_parquet(JOINED / "itspe_status.parquet", index=False)
    print("join: match methods\n" + joined["match_method"].value_counts().to_string())

    from historic_preservation.join import case_log, nomination_lots, nominations, permits, spatial

    spatial.run()
    nominations.run()
    case_log.run()
    permits.run()
    nomination_lots.run()
