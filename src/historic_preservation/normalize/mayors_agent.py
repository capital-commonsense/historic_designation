"""Mayor's Agent decisions from the Georgetown Law Library collection (manual download).

The catalog (mayors_agent_catalog.json, one record per decision) carries the
library's own metadata: issue date, HPA number, subject tags, and a description
that usually has labeled fields ("Disposition: Granted", "Date of Order: ...")
before a summary. Those summaries are the library's, a secondary source; the
decision PDFs sit beside the catalog. Where the description gives no
disposition, inputs/mayors_agent_review.csv supplies one read from the PDF,
with a quote checked against its text.
"""

import html
import json
import re
import subprocess
from pathlib import Path

import pandas as pd

from historic_preservation.config import INPUTS, NORMALIZED

LABELS = (r"(?:HPA Number|Case Name|Location(?: of Property)?|Date of (?:Decision|Order)|"
          r"Type of (?:Case/Type of )?Permit Sought|Type of Case|Disposition|Subject Matter\(s\)|Issue Areas?(?:\(s\))?|"
          r"Date of Case Summary(?:/Reviewer Name)?|Reviewer/Date of Case Summary|Reviewer|Summary(?: of Decision)?|"
          r"Building Name|Applicant)")
DISPOSITIONS = (  # first match wins
    ("partial", r"in part"),  # split decisions; approvals with conditions count as granted
    ("dismissed", r"dismiss"),
    ("delayed", r"delay"),
    ("withdrawn", r"withdrawn"),
    ("denied", r"denied|rejected"),
    ("granted", r"granted|approved|issued|cleared"),
)
# Primary case type from the library's permit type, subject tags and title; first match wins, so a
# demolition-plus-new-building project is "demolition". Decisions no rule settles are read
# (inputs/mayors_agent_type_review.csv).
CASE_TYPES = (
    ("procedural", r"Request for hearing"),
    ("demolition", r"Demoli|\braze"),
    ("subdivision", r"Subdivi"),
    ("new_construction", r"New Construction"),
    ("alteration", r"Alteration|Window|Curb Cut|siding|Facade|storefront|planter|addition"),
)
BASIS = {  # subject tag -> flag
    "special_merit": r"^Special Merit",
    "economic_hardship": r"Economic Hardship",
    "consistent_with_purposes": r"Consistent with Purposes",
    "necessary_public_interest": r"Necessary in the Public Interest",
}


def description(work: dict) -> str:
    raw = " ".join(work.get("description_tesim") or [])
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", raw))).strip()


def field(text: str, name: str) -> str:
    m = re.search(name + r"\s*:\s*(.*?)(?=\s" + LABELS + r"\s*:|$)", text)
    return m.group(1).strip() if m else ""


def classify(disposition: str) -> str:
    for name, pat in DISPOSITIONS:
        if re.search(pat, disposition, re.I):
            return name
    return "unclear" if disposition else ""


def pdf_text(path: Path) -> str:
    """Text layer, or for scans an OCR copy made once under data/normalized/ocr/mayors_agent/."""
    text = subprocess.run(["pdftotext", str(path), "-"], capture_output=True, text=True).stdout
    pages = int(re.search(r"Pages:\s+(\d+)", subprocess.run(["pdfinfo", str(path)], capture_output=True, text=True).stdout).group(1))
    if len(text.strip()) < 300 * pages:  # scans: some carry a text layer only on the certificate page
        ocr = NORMALIZED / "ocr" / "mayors_agent" / path.name
        if not ocr.exists():
            ocr.parent.mkdir(parents=True, exist_ok=True)
            subprocess.run(["ocrmypdf", "--force-ocr", "--quiet", str(path), str(ocr)], check=True)
        text = subprocess.run(["pdftotext", str(ocr), "-"], capture_output=True, text=True).stdout
    return re.sub(r"\s+", " ", text)


def decisions(folder: Path) -> pd.DataFrame:
    works = json.loads((folder / "mayors_agent_catalog.json").read_text())["works"]
    pdfs: dict[str, list[str]] = {}
    for p in sorted(folder.iterdir()):
        if "__" in p.name and p.suffix.lower() == ".pdf":  # one attachment ends in ".PDF"
            pdfs.setdefault(p.name.split("__", 1)[0], []).append(p.name)
    rows = []
    for w in works:
        t = description(w)
        subjects = w.get("subject_tesim") or []
        disposition = field(t, "Disposition")
        disposition = re.split(r"\s(?:Applicant|Issue Areas?|Date of|Reviewer)\b", disposition)[0].strip()
        rows.append({
            "work_id": w["id"],
            "title": (w.get("title_tesim") or [""])[0],
            "hpa_number": field(t, "HPA Number") or "; ".join(w.get("other_identifier_tesim") or []),
            "date_issued_catalog": (w.get("date_issued_tesim") or [""])[0],
            "date_of_order_text": field(t, "Date of (?:Decision|Order)")[:40],
            "permit_type": field(t, "Type of (?:Case/Type of )?Permit Sought")[:120],
            "disposition_text": disposition[:200],
            "disposition": classify(disposition),
            "disposition_source": "catalog description" if disposition else "",
            "subjects": "; ".join(subjects),
            **{k: any(re.search(p, s) for s in subjects) for k, p in BASIS.items()},
            "pdfs": "; ".join(pdfs.get(w["id"], [])),
            "handle": "; ".join(w.get("handle_tesim") or []),
        })
    df = pd.DataFrame(rows)
    df["order_date"] = df["date_of_order_text"].map(parse_date)
    # Catalog dates mix "1985-01-24", "1980-05" and "2015"; parse each on its own (no inferred single format).
    catalog = pd.to_datetime(df["date_issued_catalog"], errors="coerce", format="mixed")
    # The description's own order date wins; the catalog date fills gaps and is flagged when they differ.
    df["date_conflict"] = (df["order_date"].notna() & catalog.notna()
                           & ((df["order_date"] - catalog).abs().dt.days > 30))
    df["order_date"] = df["order_date"].fillna(catalog)
    df = apply_review(df, folder)
    df = apply_basis_review(df, folder)
    return apply_type_review(df, folder)


def rule_type(row) -> str:
    text = " ".join(str(x) for x in (row["permit_type"], row["subjects"], row["title"]) if isinstance(x, str))
    return next((name for name, pat in CASE_TYPES if re.search(pat, text)), "")


def apply_type_review(df: pd.DataFrame, folder: Path) -> pd.DataFrame:
    df["case_type"] = df.apply(rule_type, axis=1)
    df["case_type_source"] = df["case_type"].map(lambda t: "library permit type/subjects/title" if t else "")
    path = INPUTS / "mayors_agent_type_review.csv"
    if not path.exists():
        return df
    for r in pd.read_csv(path, dtype=str).fillna("").itertuples():
        if re.sub(r"\s+", " ", r.quote) not in pdf_text(folder / r.pdf):
            raise ValueError(f"mayors_agent_type_review.csv: quote not found in {r.pdf}: {r.quote[:60]!r}")
        hit = df["work_id"] == r.work_id
        if not hit.any():
            raise ValueError(f"mayors_agent_type_review.csv: unknown work {r.work_id}")
        if r.case_type not in {name for name, _ in CASE_TYPES}:
            raise ValueError(f"mayors_agent_type_review.csv: unknown case type {r.case_type!r}")
        df.loc[hit, ["case_type", "case_type_source"]] = [r.case_type, f"PDF review: {r.pdf}"]
    return df


def apply_basis_review(df: pd.DataFrame, folder: Path) -> pd.DataFrame:
    """Basis flags read from the PDFs for decisions the library left untagged
    (inputs/mayors_agent_basis_review.csv); quotes are checked like the disposition review."""
    df["basis_source"] = df["subjects"].map(lambda s: "library subject tags" if s else "")
    path = INPUTS / "mayors_agent_basis_review.csv"
    if not path.exists():
        return df
    for r in pd.read_csv(path, dtype=str).fillna("").itertuples():
        if re.sub(r"\s+", " ", r.quote) not in pdf_text(folder / r.pdf):
            raise ValueError(f"mayors_agent_basis_review.csv: quote not found in {r.pdf}: {r.quote[:60]!r}")
        hit = df["work_id"] == r.work_id
        if not hit.any() or df.loc[hit, "subjects"].iloc[0]:
            raise ValueError(f"mayors_agent_basis_review.csv: {r.work_id} is unknown or already tagged by the library")
        bases = {b.strip() for b in r.bases.split(";") if b.strip()}
        unknown = bases - set(BASIS)
        if unknown:
            raise ValueError(f"mayors_agent_basis_review.csv: unknown basis {unknown}")
        for b in BASIS:
            df.loc[hit, b] = b in bases
        df.loc[hit, "basis_source"] = f"PDF review: {r.pdf}" + (f" ({r.note})" if r.note else "")
    return df


DATE = re.compile(r"\d{1,2}/\d{1,2}/\d{2,4}|\d{1,2}-[A-Za-z]{3}-\d{2,4}|[A-Z][a-z]+\.? \d{1,2},? \d{4}")


def parse_date(text: str):
    m = DATE.search(text or "")
    return pd.to_datetime(m.group(0), errors="coerce") if m else pd.NaT


def apply_review(df: pd.DataFrame, folder: Path) -> pd.DataFrame:
    path = INPUTS / "mayors_agent_review.csv"
    if not path.exists():
        return df
    review = pd.read_csv(path, dtype=str).fillna("")
    df["review_note"] = ""
    for r in review.itertuples():
        text = pdf_text(folder / r.pdf)
        if re.sub(r"\s+", " ", r.quote) not in text:
            raise ValueError(f"mayors_agent_review.csv: quote not found in {r.pdf}: {r.quote[:60]!r}")
        hit = df["work_id"] == r.work_id
        if not hit.any():
            raise ValueError(f"mayors_agent_review.csv: unknown work {r.work_id}")
        df.loc[hit, ["disposition", "disposition_text", "disposition_source", "review_note"]] = [
            r.disposition, r.quote[:200], f"PDF: {r.pdf}", r.note]
    return df
