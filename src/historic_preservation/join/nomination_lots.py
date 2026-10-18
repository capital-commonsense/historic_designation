"""Link designated nominations to today's tax records, for designated value by filer type.

- District nominations: matched by name to the districts in the zoning lookup (normalized names,
  token-set score >= DISTRICT_MIN); every tax record now inside that district links.
- Landmark nominations: by address (house-number keys to lots and tax-roll addresses, as in
  join/permits.py) and by exact name to a dated GIS landmark feature (inputs/landmark_dates.csv)
  and its lots (join/spatial.py).

Amendments and boundary expansions are not linked: their added area cannot be separated from
the original designation with today's boundaries.
"""

import re

import pandas as pd
from rapidfuzz import fuzz, process

from historic_preservation import addresses
from historic_preservation.config import INPUTS, JOINED
from historic_preservation.join.permits import lot_keys

DISTRICT_MIN = 90


def district_key(name: str) -> str:
    s = re.sub(r"\(.*?\)|,.*$|\bproposed\b|\bhistoric district\b|\bnational historic site\b", " ", str(name), flags=re.I)
    return " ".join(re.sub(r"[^a-z0-9 ]", " ", s.lower()).split())


def name_key(name: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9 ]", " ", str(name).lower()).split())


def links(noms: pd.DataFrame, joined: pd.DataFrame) -> pd.DataFrame:
    rows = []
    dist_names = joined.loc[joined["in_district"], "historic_districts"].str.split(";").explode().str.strip()
    choices = {d: district_key(d) for d in dist_names.unique()}
    for r in noms[noms["kind"] == "district"].itertuples():
        best = process.extractOne(district_key(r.name), choices, scorer=fuzz.token_set_ratio)
        if best and best[1] >= DISTRICT_MIN:
            ssls = joined.loc[dist_names[dist_names == best[2]].index, "ssl"]
            rows += [(r.nomination_id, s, "district_name", best[2]) for s in ssls]

    lm = noms[noms["kind"] == "landmark"]
    keys = lm[["nomination_id", "address"]].assign(addr_key=lm["address"].map(addresses.keys)).explode("addr_key").dropna()
    by_addr = keys.merge(lot_keys(), on="addr_key")
    rows += [(r.nomination_id, r.ssl, "address", r.addr_key) for r in by_addr.itertuples()]
    dates = pd.read_csv(INPUTS / "landmark_dates.csv")
    feats = pd.read_parquet(JOINED / "landmark_lots.parquet")
    by_name = {}
    for col in ("matched_name", "gis_name"):
        for u, n in zip(dates["uniqueid"], dates[col]):
            if isinstance(n, str):
                by_name.setdefault(name_key(n), set()).add(u)
    for r in lm.itertuples():
        for u in by_name.get(name_key(r.name), ()):
            rows += [(r.nomination_id, s, "gis_name", u) for s in feats.loc[feats["feature_id"] == u, "ssl"]]
    out = pd.DataFrame(rows, columns=["nomination_id", "ssl", "method", "matched_on"])
    return out.drop_duplicates(["nomination_id", "ssl"])


def run() -> None:
    noms = pd.read_csv(JOINED / "nominations.csv")
    noms = noms[noms["outcome"].eq("designated")]
    joined = pd.read_parquet(JOINED / "itspe_status.parquet", columns=["ssl", "in_district", "historic_districts"])
    links(noms, joined).to_csv(JOINED / "nomination_lots.csv", index=False)
