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

# "Case 11-07", "HPA #12-616", a bare "#08-10" (2011 lists), or "Case #13-013" (late 2012).
CASE = re.compile(r"\b(?:Case|HP|HPA)\s*(?:No\.?|#)?\s*(\d{2})-0?(\d{2})(?!\d)"
                  r"|(?<![A-Za-z] )(?<![A-Za-z])#(\d{2})-(\d{2})(?!\d)")  # bare "#" not after a word ("Raze #07-58")


def case_no(m: re.Match) -> str:
    return f"{m.group(1) or m.group(3)}-{m.group(2) or m.group(4)}"
VOTE = re.compile(r"Vote:?\s*(\d+)\s*[-–]\s*(\d+)")
OUTCOMES = (  # first match wins; order matters
    ("withdrawn", r"withdr[ae]w|was withdrawn"),
    ("denied", r"not to (?:approve|designate|recommend)|voted against designat|denied|declined to designate|did not (?:approve|designate)"
               r"|denying the (?:application|nomination|designation)"),
    ("continued", r"continued|deferred|postponed|took no action|no action|record will remain open|held open|tabled"
                  r"|prior to deliberating|nomination be revised|return to the Board"),
    ("amended", r"approve[ds]? (?:the|an) amendment|amended|additional documentation"),
    ("designated", r"designat|nomination approved|approve[ds]? the nomination|voted to approve"
                   r"|approved the (?:landmark|historic district|application)"),
)
# Statements that apply one action to a following list of cases (consent calendars).
BLOCK_ACTION = re.compile(r"(?:consent calendar|following (?:cases|items|nominations|properties) were|"
                          r"approved the following)[^.]*\.", re.I)
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
        # Headers that wrap start on earlier flush-left lines; action text is indented.
        for _ in range(3):
            prev_start = flat.rfind("\n", 0, max(line_start - 1, 0)) + 1
            prev = flat[prev_start: line_start - 1]
            if (not prev.strip() or prev[:1].isspace() or prev.strip().isupper() or VOTE.search(prev)
                    or prev.rstrip().endswith(".") or CASE.search(prev)):
                break
            line_start = prev_start
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
        basis = "item text" if outcome != "unclear" else ""
        if outcome == "unclear":
            # Use a block statement (e.g. consent calendar) between the previous vote and this item.
            before = flat[max(0, line_start - 2500): line_start]
            last_vote = max((m2.end() for m2 in VOTE.finditer(before)), default=0)
            block = BLOCK_ACTION.findall(before[last_vote:])
            if block:
                for name, pat in OUTCOMES:
                    if re.search(pat, block[-1], re.I) or (name == "designated" and re.search(r"approved", block[-1], re.I)):
                        outcome, phrase, basis = name, block[-1].strip()[:200], "block statement (inferred)"
                        break
        rec = STAFF_REC.search(body)
        out.append({
            "case_no": case_no(m),
            "header": re.sub(r"\s+", " ", header)[:300],
            "action_text": body[:1500],
            "outcome": outcome,
            "outcome_phrase": phrase,
            "outcome_basis": basis,
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
