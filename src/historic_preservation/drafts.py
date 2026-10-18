"""Draft hand-curated inputs from parsed sources, for review before they go in inputs/.

Drafts are written to data/drafts/ and never overwrite inputs/. After review,
the curated file is copied to inputs/ and edited by hand from then on.

    uv run python -m historic_preservation.drafts landmarks
"""

import re
import sys

import pandas as pd
from rapidfuzz import fuzz, process

from historic_preservation.config import DATA, INPUTS, JOINED, NORMALIZED

DRAFTS = DATA / "drafts"
DATE_FMT = "%B %d, %Y"


def norm_name(s: str) -> str:
    s = s.lower().replace("’", "'").replace("&", " and ")
    s = re.sub(r"\[.*?\]", " ", s)  # [National Register only], [demolished]
    s = re.sub(r"\b(the|and|of)\b", " ", s)
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _first(s) -> str:
    return s.split("; ")[0] if isinstance(s, str) and s else ""


def inventory_candidates() -> pd.DataFrame:
    """One row per 2009 Inventory entry with its first DC date and basis."""
    inv = pd.read_csv(NORMALIZED / "inventory_2009_entries.csv")
    rows = []
    for r in inv.itertuples():
        text = r.text if isinstance(r.text, str) else ""
        designated, listing = _first(r.dc_designation), _first(r.dc_listing)
        preliminary = bool(re.search(r"preliminary", text, re.I))
        if listing and not (preliminary and designated):
            date, basis = listing, "dc_listing"
        elif designated:
            date, basis = designated, "designated"
        else:
            date, basis = "", ""
        if designated and listing and not preliminary:
            # Listed, then later designated (e.g. after omission): keep the first date.
            date, basis = listing, "dc_listing"
        flags = []
        if isinstance(r.omitted, str) and r.omitted:
            flags.append(f"omitted {r.omitted}")
        if re.search(r"NR (only|eligible)|\[National Register|\[NR only", r.name):
            flags.append("NR-only or NR-eligible entry")
        rows.append({
            "cand_name": r.name,
            "address": text[:160],
            "first_date": pd.to_datetime(date, format=DATE_FMT, errors="coerce") if date else pd.NaT,
            "basis": basis,
            "effective": pd.to_datetime(_first(r.effective), format=DATE_FMT, errors="coerce"),
            "nominated_by": "",
            "source_doc": "inventory_2009",
            "source_page": r.page,
            "flags": "; ".join(flags),
        })
    return pd.DataFrame(rows)


def update_candidates() -> pd.DataFrame:
    items = pd.read_csv(NORMALIZED / "inventory_update_items.csv")
    items = items[items["designated"].notna()]
    out = pd.DataFrame({
        "cand_name": items["name"],
        "address": items["address"],
        "first_date": pd.to_datetime(items["designated"], format=DATE_FMT, errors="coerce"),
        "basis": "designated",
        "effective": pd.to_datetime(items["effective"], format=DATE_FMT, errors="coerce"),
        "nominated_by": items["nominated_by"].fillna(""),
        "source_doc": items["source_doc"],
        "source_page": items["page"],
        "flags": "",
    })
    fy10 = pd.read_csv(INPUTS / "manual_designations.csv", parse_dates=["designated", "effective"])
    out10 = pd.DataFrame({
        "cand_name": fy10["name"],
        "address": fy10["address"],
        "first_date": fy10["designated"],
        "basis": "designated",
        "effective": fy10["effective"],
        "nominated_by": fy10["nominated_by"].fillna(""),
        "source_doc": fy10["source_doc"],
        "source_page": fy10["source_page"],
        "flags": fy10["notes"].fillna(""),
    })
    return pd.concat([out, out10], ignore_index=True)


def hprb_candidates() -> pd.DataFrame:
    """HPRB designation actions, for explicit overrides only (not automatic matching)."""
    acts = pd.read_csv(NORMALIZED / "hprb_designation_actions.csv", parse_dates=["meeting_date"])
    acts = acts[acts["outcome"] == "designated"]
    return pd.DataFrame({
        "cand_name": acts["header"].str.replace(r",?\s*(?:Cases?|HP Case)\s*(?:No\.?|#)?\s*\d.*$", "", regex=True).str.strip(),
        "address": acts["header"],
        "first_date": acts["meeting_date"],
        "basis": "designated",
        "effective": pd.NaT,
        "nominated_by": "",
        "source_doc": "hprb_actions",
        "source_page": "case " + acts["case_no"] + " (" + acts["source_file"] + ")",
        "flags": "",
    })


def gis_landmarks() -> pd.DataFrame:
    pts = pd.read_csv(NORMALIZED / "landmark_points.csv")
    polys = pd.read_csv(NORMALIZED / "landmark_polygons.csv")
    cols = ["uniqueid", "name", "label", "shortlabel", "status"]
    both = pd.concat([pts[cols], polys[cols]]).drop_duplicates("uniqueid")
    return both.sort_values("uniqueid").reset_index(drop=True)


def address_keys(text) -> set[tuple[str, str]]:
    """(house number, first street word) pairs, e.g. '1072 and 1074 Thomas Jefferson St' ->
    {('1072','thomas'), ('1074','thomas')}."""
    if not isinstance(text, str):
        return set()
    keys = set()
    for m in re.finditer(r"((?:\d+[A-Z]?(?:\s*(?:-|and|&|,)\s*)?)+)\s+([A-Za-z0-9]+)", text):
        street = m.group(2).lower()
        if street in {"and", "to", "through"}:
            continue
        for num in re.findall(r"\d+", m.group(1)):
            keys.add((num, re.sub(r"(st|nd|rd|th)$", "", street)))
    return keys


def gis_addresses(gis: pd.DataFrame) -> dict[str, set]:
    """Lot addresses for each GIS landmark: lots it covers spatially, plus lots
    whose Zoning Lookup landmark label names it."""
    zl = pd.read_parquet(NORMALIZED / "zoning_lookup.parquet", columns=["ssl", "landmark_label", "address"])
    keys_by_ssl = zl.set_index("ssl")["address"].map(address_keys)
    keys_by_ssl = keys_by_ssl[~keys_by_ssl.index.duplicated()]
    lots = zl.dropna(subset=["landmark_label"]).assign(lab=lambda d: d["landmark_label"].str.split(";")).explode("lab")
    by_label = lots.groupby(lots["lab"].str.strip())["address"].agg(lambda s: set().union(*map(address_keys, s)))
    spatial = pd.read_parquet(JOINED / "landmark_lots.parquet")
    by_feature = spatial.groupby("feature_id")["ssl"].agg(
        lambda s: set().union(*(keys_by_ssl.get(x, set()) for x in s))
    )
    out = {}
    for g in gis.itertuples():
        keys = set(by_feature.get(g.uniqueid, set()))
        for lab in (g.name, g.label, g.shortlabel):
            if isinstance(lab, str) and lab in by_label.index:
                keys |= by_label[lab]
        out[g.uniqueid] = keys
    return out


def match(gis: pd.DataFrame, cands: pd.DataFrame) -> pd.DataFrame:
    keys = cands["cand_name"].map(norm_name).tolist()
    cand_addr = cands["address"].map(address_keys).tolist()
    addrs = gis_addresses(gis)
    rows = []
    for g in gis.itertuples():
        scored: dict[int, float] = {}
        for q in (g.name, g.label):
            if not isinstance(q, str):
                continue
            for scorer, penalty in ((fuzz.token_sort_ratio, 0), (fuzz.token_set_ratio, 5)):
                for _, score, idx in process.extract(norm_name(q), keys, scorer=scorer, limit=5):
                    scored[idx] = max(scored.get(idx, 0), score - penalty)  # token_set over-rewards subsets
        best_idx = max(scored, key=scored.get)
        addr_hit = [i for i in scored if addrs[g.uniqueid] & cand_addr[i] and scored[i] >= 50]
        if addr_hit:
            best_idx = max(addr_hit, key=scored.get)
        c = cands.iloc[best_idx]
        rows.append({
            "uniqueid": g.uniqueid,
            "gis_name": g.name,
            "gis_status": g.status,
            "matched_name": c["cand_name"],
            "match_score": round(scored[best_idx], 1),
            "address_match": bool(addr_hit),
            **c.drop(["cand_name", "address"]).to_dict(),
        })
    return pd.DataFrame(rows)


def landmarks() -> None:
    gis = gis_landmarks()
    inv, upd = inventory_candidates(), update_candidates()
    m_inv, m_upd = match(gis, inv), match(gis, upd)
    # Prefer the 2009 Inventory unless the update matches clearly better.
    use_upd = (m_upd["match_score"] > m_inv["match_score"] + 3) | (
        m_inv["first_date"].isna() & (m_upd["match_score"] >= 90)
    )
    out = m_inv.where(~use_upd, m_upd)
    out["confidence"] = pd.cut(out["match_score"], [-1, 85, 95, 101], labels=["low", "medium", "high"]).astype(str)
    out.loc[out["address_match"] & (out["match_score"] >= 70), "confidence"] = "high"
    out.loc[out["first_date"].isna(), "confidence"] = "low"
    out["review"] = out["confidence"] != "high"
    DRAFTS.mkdir(parents=True, exist_ok=True)
    out.to_csv(DRAFTS / "landmark_dates_draft.csv", index=False, date_format="%Y-%m-%d")
    print(out["confidence"].value_counts().to_string())

    final = apply_review(out, pd.concat([inv, upd, hprb_candidates()], ignore_index=True))
    final.to_csv(INPUTS / "landmark_dates.csv", index=False, date_format="%Y-%m-%d")
    print(f"wrote inputs/landmark_dates.csv: {final['first_date'].notna().sum()} of {len(final)} dated")


REVIEW_COLS = ["uniqueid", "gis_name", "gis_status", "matched_name", "first_date", "basis", "effective",
               "nominated_by", "source_doc", "source_page", "match_score", "match_decision", "confidence", "flags"]


def apply_review(draft: pd.DataFrame, cands: pd.DataFrame) -> pd.DataFrame:
    """Apply inputs/landmark_match_review.csv (accept / reject / override / unmatched) to the draft.

    "unmatched" is a checked absence: no source has a designation record; the note says what was searched.
    """
    review = pd.read_csv(INPUTS / "landmark_match_review.csv")
    if review["uniqueid"].duplicated().any():
        raise ValueError(f"landmark_match_review.csv: duplicate rows for {sorted(review.loc[review['uniqueid'].duplicated(), 'uniqueid'])}")
    review = review.set_index("uniqueid")
    out = draft.astype({"source_page": "object", "flags": "object", "nominated_by": "object"})
    out["match_decision"] = "auto"
    for uid, r in review.iterrows():
        i = out.index[out["uniqueid"] == uid]
        if len(i) == 0:
            continue
        i = i[0]
        out.loc[i, "match_decision"] = r["decision"]
        if r["decision"] == "accept":
            out.loc[i, "confidence"] = r["confidence"]
        elif r["decision"] in ("reject", "unmatched"):
            for col in ("matched_name", "basis", "nominated_by", "source_doc", "source_page", "flags"):
                out.loc[i, col] = ""
            out.loc[i, ["first_date", "effective"]] = pd.NaT
            out.loc[i, "confidence"] = "unmatched"
            if r["decision"] == "unmatched":
                out.loc[i, "flags"] = r["note"]
        else:
            c = cands[(cands["cand_name"] == r["candidate_name"]) & (cands["source_doc"] == r["candidate_source"])]
            c = c.tail(1)  # hand-read rows (inputs/manual_designations.csv) come last and win
            if len(c) != 1:
                raise ValueError(f"override for {uid}: {len(c)} candidates named {r['candidate_name']!r}")
            c = c.iloc[0]
            out.loc[i, "matched_name"] = c["cand_name"]
            for col in ("first_date", "basis", "effective", "nominated_by", "source_doc", "source_page"):
                out.loc[i, col] = c[col]
            out.loc[i, "flags"] = "; ".join(x for x in (c["flags"], r["note"]) if isinstance(x, str) and x)
            out.loc[i, "confidence"] = r["confidence"]
    out.loc[out["first_date"].isna() & (out["confidence"] != "unmatched"), "confidence"] = "no_dc_date"
    return out[REVIEW_COLS]


if __name__ == "__main__":
    {"landmarks": landmarks}[sys.argv[1]]()
