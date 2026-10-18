"""Link individual-landmark nominations to permits issued at the same lots (H2).

A nomination's address text is expanded to standardized addresses, those to
today's lots (SSL) through the zoning lookup and the tax roll, and a permit
links when its SSL or its own address matches. Districts are left out: a
district nomination covers too many lots for a permit to say anything about it.
"""

import re

import pandas as pd

from historic_preservation import addresses
from historic_preservation.config import INPUTS, JOINED, NORMALIZED, snapshot_dir

KINDS = ("landmark", "landmark_amendment")
WINDOW_YEARS = 3


def lot_keys() -> pd.DataFrame:
    """addr_key -> ssl from the zoning lookup and the tax roll."""
    zl = pd.read_parquet(NORMALIZED / "zoning_lookup.parquet", columns=["ssl", "address"])
    itspe = pd.read_parquet(NORMALIZED / "itspe.parquet", columns=["ssl", "premiseadd"])
    rows = [(k, ssl) for ssl, a in zip(zl["ssl"], zl["address"]) for k in addresses.keys(a)]
    rows += [(k, ssl) for ssl, a in zip(itspe["ssl"], itspe["premiseadd"]) for k in addresses.keys(a)]
    return pd.DataFrame(rows, columns=["addr_key", "ssl"]).dropna().drop_duplicates()


def reference_dates(noms: pd.DataFrame, actions: pd.DataFrame) -> pd.DataFrame:
    """Each nomination's first HPRB hearing; else its outcome date.

    Filing comes before the hearing, usually by months, and the open data has no
    filing date. Outcome dates on October 1 that come from an annual report stand
    for a fiscal year, not a day, and are flagged.
    """
    first_hearing = actions.dropna(subset=["case_no"]).groupby("case_no")["meeting_date"].min()
    hearing = noms["case_no"].map(first_hearing)
    approx = hearing.isna() & noms["outcome_date"].str.endswith("-10-01", na=False) & ~noms["seen_in"].eq("hprb")
    return pd.DataFrame({
        "nomination_id": noms["nomination_id"],
        "ref_date": hearing.fillna(noms["outcome_date"]),
        "ref_date_basis": hearing.notna().map({True: "first_hearing", False: "outcome_date"}).where(~approx, "fiscal_year_only"),
    })


def nomination_permits(noms: pd.DataFrame, permits: pd.DataFrame, lots: pd.DataFrame) -> pd.DataFrame:
    """Permits issued within WINDOW_YEARS of each nomination's reference date. noms carries ref_date."""
    noms = noms[noms["kind"].isin(KINDS) & noms["address"].notna()]
    keys = noms[["nomination_id", "address"]].assign(addr_key=noms["address"].map(addresses.keys)).explode("addr_key")
    keys = keys[keys["addr_key"].notna()]
    by_ssl = keys.merge(lots, on="addr_key")[["nomination_id", "ssl"]].drop_duplicates()
    hits = pd.concat([
        by_ssl.merge(permits, on="ssl").assign(matched_on="ssl"),
        keys[["nomination_id", "addr_key"]].merge(permits, on="addr_key").assign(matched_on="address"),
    ])
    hits = hits.sort_values("matched_on", ascending=False).drop_duplicates(["nomination_id", "permit_id"])
    meta = noms.set_index("nomination_id")[["case_no", "name", "address", "outcome", "ref_date", "ref_date_basis"]]
    out = hits[["nomination_id", "permit_id", "issued", "subtype", "status", "address", "ssl", "desc_of_work", "matched_on"]]
    out = out.rename(columns={"address": "permit_address"}).join(meta, on="nomination_id")
    out["days_from_ref"] = (pd.to_datetime(out["issued"]) - pd.to_datetime(out["ref_date"])).dt.days
    out = out[out["days_from_ref"].abs() <= WINDOW_YEARS * 366]
    cols = ["nomination_id", "case_no", "name", "address", "outcome", "ref_date", "ref_date_basis", "permit_id", "issued",
            "days_from_ref", "subtype", "status", "permit_address", "ssl", "matched_on", "desc_of_work"]
    return out[cols].sort_values(["nomination_id", "issued"]).reset_index(drop=True)


def matched_nominations(noms: pd.DataFrame, lots: pd.DataFrame) -> pd.DataFrame:
    """Which nominations resolved to at least one lot or address (the denominator's coverage)."""
    noms = noms[noms["kind"].isin(KINDS)]
    k = noms["address"].map(addresses.keys)
    lot_set = set(lots["addr_key"])
    return pd.DataFrame({
        "nomination_id": noms["nomination_id"],
        "ref_date": noms["ref_date"],
        "ref_date_basis": noms["ref_date_basis"],
        "outcome": noms["outcome"],
        "has_address_key": k.map(bool),
        "has_lot": k.map(lambda ks: any(x in lot_set for x in ks)),
    })


def _source_text(source_file: str) -> str:
    from historic_preservation.normalize.hprb import BOX, doc_text, html_text

    if source_file.startswith("box:"):
        return doc_text(BOX / source_file[4:])
    hprb = snapshot_dir() / "hprb"
    pdf = hprb / "attachments" / source_file
    return doc_text(pdf) if pdf.exists() else html_text(hprb / "pages" / source_file)


def pending_applications(noms: pd.DataFrame) -> pd.DataFrame:
    """inputs/h2_pending_applications.csv, quotes checked, joined to nominations by case number.

    Each row is a raze or alteration application the HPRB documents show was pending
    while a landmark nomination for the same property was. The documents rarely say
    which came first; `order` records it only where one does.
    """
    review = pd.read_csv(INPUTS / "h2_pending_applications.csv", dtype=str).fillna("")
    texts: dict[str, str] = {}
    for r in review.itertuples():
        if r.source_file not in texts:
            texts[r.source_file] = re.sub(r"\s+", " ", _source_text(r.source_file)).replace("^(st)", "st")
        if re.sub(r"\s+", " ", r.quote) not in texts[r.source_file]:
            raise ValueError(f"h2_pending_applications.csv: quote not found in {r.source_file}: {r.quote[:60]!r}")
    dupes = review["case_no"].duplicated(keep=False)
    if dupes.any():
        raise ValueError(f"h2_pending_applications.csv: repeated cases {sorted(set(review.loc[dupes, 'case_no']))}")
    known = noms.dropna(subset=["case_no"]).drop_duplicates("case_no").set_index("case_no")
    out = review.join(known[["nomination_id", "kind", "outcome", "outcome_date", "ref_date"]], on="case_no")
    out["in_nominations"] = out["nomination_id"].notna()
    return out


def run() -> None:
    path = NORMALIZED / "permits.csv"
    if not path.exists() or path.stat().st_size < 10:
        return
    permits = pd.read_csv(path, dtype={"ssl": "string"})
    noms = pd.read_csv(JOINED / "nominations.csv")
    noms = noms.merge(reference_dates(noms, pd.read_csv(NORMALIZED / "hprb_designation_actions.csv")), on="nomination_id")
    lots = lot_keys()
    nomination_permits(noms, permits, lots).to_csv(JOINED / "nomination_permits.csv", index=False)
    matched_nominations(noms, lots).to_csv(JOINED / "nomination_lot_match.csv", index=False)
    pending_applications(noms).to_csv(JOINED / "h2_pending_applications.csv", index=False)
