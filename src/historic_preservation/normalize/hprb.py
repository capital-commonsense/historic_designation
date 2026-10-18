"""Extract designation actions from HPRB meeting records.

Designation cases are numbered "YY-NN" (two-digit suffix), e.g. "Case 25-03"
or "HP #08-14"; permit cases are "HPA YY-NNN". For each designation case
mentioned in a meeting's actions, keep the item header (name, address), the
action text up to the vote, a coarse outcome class, the vote, and any stated
HPO/staff recommendation. Outcome classes are inferred from the wording and
the matched phrase is kept so each one can be checked.
"""

import html as htmllib
import re
import subprocess
from datetime import datetime
from pathlib import Path

import pandas as pd

CASE = re.compile(r"\b(?:Case|HP|HPA)\s*(?:No\.?|#)?\s*(\d{2})-(\d{2})(?!\d)")
VOTE = re.compile(r"Vote:?\s*(\d+)\s*[-–]\s*(\d+)")
OUTCOMES = (  # first match wins; order matters
    ("withdrawn", r"withdr[ae]w|was withdrawn"),
    ("denied", r"not to (?:approve|designate|recommend)|voted against designat|denied|declined to designate|did not (?:approve|designate)"),
    ("continued", r"continued|deferred|postponed|took no action|no action|record will remain open|held open|tabled"),
    ("amended", r"approve[ds]? the amendment|amended|additional documentation"),
    ("designated", r"designat|approve[ds]? the nomination|voted to approve|approved the (?:landmark|historic district|application)"),
)
STAFF_REC = re.compile(r"(?:The )?(?:HPO|staff|Historic Preservation Office) recommend\w*[^.]*\.", re.I)
MONTHS = "january|february|march|april|may|june|july|august|september|october|november|december"


def html_text(path: Path) -> str:
    t = path.read_text(errors="ignore")
    m = re.search(r'id="content-start".*?(?=class="zone-postscript|<footer)', t, re.S)
    body = m.group(0) if m else t
    body = re.sub(r"<(script|style).*?</\1>", "", body, flags=re.S)
    body = re.sub(r"<br\s*/?>|</p>|</div>|</h\d>|</li>", "\n", body)
    return htmllib.unescape(re.sub(r"<[^>]+>", " ", body))


def pdf_text(path: Path) -> str:
    return subprocess.run(["pdftotext", "-layout", str(path), "-"], capture_output=True, text=True).stdout


def meeting_date(slug: str, text: str):
    m = re.search(rf"({MONTHS})[ -](\d{{1,2}})(?:,| )+(\d{{4}})", f"{slug.replace('-', ' ')} {text[:600]}", re.I)
    if m:
        try:
            return datetime.strptime(f"{m.group(1)} {m.group(2)} {m.group(3)}", "%B %d %Y").date()
        except ValueError:
            pass
    m = re.search(rf"({MONTHS})[ -](\d{{4}})", slug, re.I)
    return datetime.strptime(f"{m.group(1)} 1 {m.group(2)}", "%B %d %Y").date() if m else None


def items(text: str) -> list[dict]:
    flat = re.sub(r"[ \t]+", " ", text)
    flat = re.sub(r"\n\s*\d+\s*\n|1100 4 ?th Street SW.*?\n", "\n", flat)  # page numbers, letterhead
    out = []
    hits = [m for m in CASE.finditer(flat) if not re.match(r"\s*HPA", m.group(0))]
    for i, m in enumerate(hits):
        line_start = flat.rfind("\n", 0, m.start()) + 1
        header = flat[line_start: flat.find("\n", m.end()) if "\n" in flat[m.end():] else len(flat)].strip()
        end = hits[i + 1].start() if i + 1 < len(hits) else len(flat)
        nxt_permit = re.search(r"\n[^\n]*HPA\s*#?\s*\d{2}-\d{3}", flat[m.end():end])
        if nxt_permit:
            end = m.end() + nxt_permit.start()
        body = flat[m.end(): end]
        vote = VOTE.search(body)
        if vote:
            body = body[: vote.end()]
        body = re.sub(r"\s+", " ", body).strip()
        outcome, phrase = "unclear", ""
        for name, pat in OUTCOMES:
            hit = re.search(pat, body, re.I)
            if hit:
                outcome, phrase = name, hit.group(0)
                break
        rec = STAFF_REC.search(body)
        out.append({
            "case_no": f"{m.group(1)}-{m.group(2)}",
            "header": re.sub(r"\s+", " ", header)[:300],
            "action_text": body[:1500],
            "outcome": outcome,
            "outcome_phrase": phrase,
            "vote_for": int(vote.group(1)) if vote else None,
            "vote_against": int(vote.group(2)) if vote else None,
            "staff_recommendation": rec.group(0).strip() if rec else "",
        })
    return out


def extract(hprb_dir: Path) -> pd.DataFrame:
    import json
    index = json.loads((hprb_dir / "index.json").read_text())
    by_slug: dict[str, list[str]] = {}
    for name, f in index["files"].items():
        if "sha256" in f:
            by_slug.setdefault(f["slug"], []).append(name)
    rows = []
    for slug, names in by_slug.items():
        actions = [n for n in names if n.lower().endswith(".pdf") and re.search(r"action", n, re.I)]
        sources = [(n, pdf_text(hprb_dir / "attachments" / n)) for n in actions]
        page = next((n for n in names if n.endswith(".html")), None)
        if not sources and page:
            sources = [(page, html_text(hprb_dir / "pages" / page))]
        for source, text in sources:
            date = meeting_date(slug, text)
            for it in items(text):
                rows.append({"meeting_date": date, "slug": slug, "source_file": source, **it})
    df = pd.DataFrame(rows)
    return df.drop_duplicates(["meeting_date", "case_no", "action_text"]) if len(df) else df
