"""DC Court of Appeals opinions (CourtListener) -> court_opinions.csv and court_cases.csv.

The CourtListener queries are broad ("Don't Tear It Down" matches many
unrelated cases), so every opinion gets term counts and a relevance flag.
The preservation cases are coded by hand in inputs/court_cases.csv; each
row's holding_quote must appear verbatim in the opinion text, which this
module checks.
"""

import html
import json
import re
from pathlib import Path

import pandas as pd

from historic_preservation.config import INPUTS

TERMS = {
    "mayors_agent": r"Mayor['’]?s [Aa]gent",
    "hprb": r"Historic Preservation Review Board|\bHPRB\b",
    "act": r"Historic Landmark and Historic District Protection Act|D\.C\. Law 2-144|\b6-11\d\d|\b5-10\d\d",
    "special_merit": r"special merit",
    "economic_hardship": r"unreasonable economic hardship",
    "dcpl": r"Preservation League|Don['’]?t Tear It Down",
}
RELEVANT_MIN = 3  # mayors_agent + hprb + act mentions


def squash(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def opinion_text(o: dict) -> str:
    t = o.get("plain_text") or re.sub(r"<[^>]+>", " ", o.get("html_with_citations") or "")
    return squash(html.unescape(t))


def texts(dest: Path) -> dict[str, str]:
    """Cluster id -> all opinion text in the cluster (lead, concurrences, dissents)."""
    manifest = json.loads((dest / "manifest.json").read_text())
    out: dict[str, list[str]] = {}
    for name, m in sorted(manifest.items()):
        if "sha256" in m:
            out.setdefault(m["cluster_id"], []).append(opinion_text(json.loads((dest / name).read_text())))
    return {cid: " ".join(ts) for cid, ts in out.items()}


def opinions(dest: Path) -> pd.DataFrame:
    clusters = json.loads((dest / "search_results.json").read_text())
    body = texts(dest)
    rows = []
    for cid, r in clusters.items():
        t = body.get(cid, "")
        counts = {k: len(re.findall(p, t, re.I)) for k, p in TERMS.items()}
        rows.append({
            "cluster_id": cid, "decided": r.get("dateFiled"), "docket": r.get("docketNumber"),
            "case_name": r.get("caseName"), "text_fetched": bool(t), **counts,
            "relevant": counts["mayors_agent"] + counts["hprb"] + counts["act"] >= RELEVANT_MIN,
            "matched_queries": "; ".join(sorted(set(r.get("matched_queries", [])))),
            "url": f"https://www.courtlistener.com{r['absolute_url']}" if r.get("absolute_url") else "",
        })
    out = pd.DataFrame(rows).sort_values(["decided", "cluster_id"])
    # Relevant but uncoded = zoning/BZA/FOIA cases where preservation is incidental.
    out["coded"] = out["cluster_id"].isin(pd.read_csv(INPUTS / "court_cases.csv", dtype=str)["cluster_id"])
    return out


def cases(dest: Path) -> pd.DataFrame:
    """Hand-coded preservation cases, with docket/date from the search results and quotes verified."""
    coded = pd.read_csv(INPUTS / "court_cases.csv", dtype=str).fillna("")
    clusters = json.loads((dest / "search_results.json").read_text())
    body = texts(dest)
    missing = [q for cid, q in zip(coded["cluster_id"], coded["holding_quote"]) if squash(q) not in body.get(cid, "")]
    if missing:
        raise ValueError(f"court_cases.csv: holding_quote not found in opinion text: {missing}")
    coded.insert(1, "decided", coded["cluster_id"].map(lambda c: clusters[c].get("dateFiled")))
    coded.insert(2, "docket", [comp or clusters[c].get("docketNumber") for c, comp in zip(coded["cluster_id"], coded["component"])])
    coded["agency_order_date"] = pd.to_datetime(coded["agency_order_date"], errors="coerce")
    coded["days_order_to_opinion"] = (pd.to_datetime(coded["decided"]) - coded["agency_order_date"]).dt.days
    return coded.drop(columns="component")
