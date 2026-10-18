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

from historic_preservation.config import INPUTS

# "Case 11-07", "Cases 17-14 and 17-21", "HPA #12-616", a bare "#08-10" (2011 lists),
# "Case #13-013" (late 2012), or a header ending ", 22-09." (2022).
CASE = re.compile(r"\b(?:Cases?|HP|HPA)\s*(?:No\.?|#)?\s*(\d{2})-0?(\d{2})(?!\d)"
                  r"|(?<![A-Za-z] )(?<![A-Za-z])#(\d{2})-(\d{2})(?!\d)"  # bare "#" not after a word ("Raze #07-58")
                  r"|(?<=, )(\d{2})-(\d{2})(?=\.?[ \t]*$)", re.M)


def case_no(m: re.Match) -> str:
    groups = m.groups()
    return next(f"{a}-{b}" for a, b in zip(groups[::2], groups[1::2]) if a)


class Hit:
    """A case header found in the text: by its printed number, or by a hand anchor (no number printed)."""

    def __init__(self, start: int, end: int, case: str, text: str):
        self.start, self.end, self.case, self.text = start, end, case, text


VOTE = re.compile(r"Vote:?\s*(\d+)\s*[-–]\s*(\d+)")
OUTCOMES = (  # first match wins; order matters
    ("withdrawn", r"withdr[ae]w|was withdrawn"),
    ("denied", r"not to (?:approve|designate|recommend)|voted against designat|denied|declined to designate|did not (?:approve|designate)"
               r"|denying the (?:application|nomination|designation)"),
    ("continued", r"continued|deferred|postponed|took no action|no action|record will remain open|held open|tabled"
                  r"|prior to deliberating|nomination be revised|return to the Board|abeyance|wishes to proceed"),
    ("amended", r"approve[ds]? (?:the|an) amendment|amended|additional documentation"
                r"|boundaries (?:increased|expanded|extended)|voted to expand the (?:boundar|period)"),
    ("designated", r"designat|nomination (?:was )?approved|approve[ds]? the nomination|voted to approve"
                   r"|approved the (?:landmark|historic district|application)|\blisted\b.{0,80}?Inventory"),
)
# Statements that apply one action to a following list of cases (consent calendars).
BLOCK_ACTION = re.compile(r"(?:consent calendar|following (?:cases|items|nominations|properties) were|"
                          r"approved the following)[^.:]*[.:]", re.I)  # "... consent calendar on July 27:"
# ... and statements that follow the list they apply to: "designated the above-listed properties"
# (March 2011), "designated the five properties" (Jan 2011), "Designated by a vote of 8-0" (Jan 2010).
BLOCK_AFTER = re.compile(r"[^.]*\b(?:above[- ]listed|these (?:nominations|properties|buildings|landmarks)"
                         r"|the (?:two|three|four|five|six|seven|eight|nine|ten|\d+) (?:properties|buildings|nominations|landmarks)"
                         r"|^Designated by a vote)[^.]*\.", re.I | re.M)
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
    # Two-day meetings are dated by their last day: "October 24 and October 31, 2013", "April 23 and 30, 2015".
    m = re.search(rf"({MONTHS})[ -](?:\d{{1,2}} and )?(\d{{1,2}})(?:,| )+(\d{{4}})", f"{slug.replace('-', ' ')} {text[:600]}", re.I)
    if m:
        try:
            return datetime.strptime(f"{m.group(1)} {m.group(2)} {m.group(3)}", "%B %d %Y").date()
        except ValueError:
            pass
    m = re.search(rf"({MONTHS})[ -](\d{{4}})", slug, re.I)
    return datetime.strptime(f"{m.group(1)} 1 {m.group(2)}", "%B %d %Y").date() if m else None


def items(text: str, anchors: list[tuple[str, str]] = ()) -> list[dict]:
    """anchors: (header start, case no.) for designation items printed without a case number."""
    flat = re.sub(r"[ \t]+", " ", text)
    flat = re.sub(r"\n\s*\d+\s*\n|1100 4 ?th Street SW.*?\n", "\n", flat)  # page numbers, letterhead
    out = []
    hits = [Hit(m.start(), m.end(), case_no(m), m.group(0)) for m in CASE.finditer(flat) if not re.match(r"\s*HPA", m.group(0))]
    for header_start, case in anchors:
        a = re.search(r"\s+".join(map(re.escape, header_start.split())), flat)
        if not a:
            raise ValueError(f"hprb_case_anchors.csv: {header_start!r} not found")
        hits.append(Hit(a.start(), flat.find("\n", a.end()), case, a.group(0)))
    hits.sort(key=lambda h: h.start)
    for i, m in enumerate(hits):
        line_start = flat.rfind("\n", 0, m.start) + 1
        # Headers that wrap start on earlier flush-left lines; action text is indented.
        for _ in range(3):
            prev_start = flat.rfind("\n", 0, max(line_start - 1, 0)) + 1
            prev = flat[prev_start: line_start - 1]
            if (not prev.strip() or prev[:1].isspace() or prev.strip().isupper() or VOTE.search(prev)
                    or prev.rstrip().endswith(".") or CASE.search(prev)):
                break
            line_start = prev_start
        header = flat[line_start: flat.find("\n", m.end) if "\n" in flat[m.end:] else len(flat)].strip()
        end = hits[i + 1].start if i + 1 < len(hits) else len(flat)
        nxt_permit = re.search(r"\n[^\n]*HPA\s*#?\s*\d{2}-\d{3}", flat[m.end:end])
        if nxt_permit:
            end = m.end + nxt_permit.start()
        body = flat[m.end: end]
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
            # A list's closing statement can follow several items, so read to the next section heading.
            heading = re.search(r"\n[A-Z][A-Z ,/&'’-]{6,}\n", flat[m.end:])
            after = flat[m.end: m.end + heading.start() if heading else len(flat)]
            follow = BLOCK_AFTER.search(after)
            # Another item's vote in between means the statement isn't ours, unless it names the list
            # explicitly ("above-listed"; March 2011 has the MPD's own vote first).
            if follow and (not VOTE.search(after[: follow.start()]) or re.search(r"above[- ]listed", follow.group(0), re.I)):
                for name, pat in OUTCOMES:
                    if re.search(pat, follow.group(0), re.I) or (name == "designated" and re.search(r"approv|passed", follow.group(0), re.I)):
                        outcome, phrase, basis = name, re.sub(r"\s+", " ", follow.group(0)).strip()[:200], "following block statement (inferred)"
                        break
        if outcome == "unclear":
            # Use the last block statement (e.g. consent calendar) before this item, unless another
            # item's vote comes between them. The statement often carries its own vote ("... Vote: 5-0.").
            before = flat[max(0, line_start - 2500): line_start]
            blocks = list(BLOCK_ACTION.finditer(before))
            tail = before[blocks[-1].end():] if blocks else ""
            own_vote = re.match(r"\s*(?:Vote:?\s*)?\d+\s*[-–]\s*\d+\.?", tail)
            block = [blocks[-1].group(0)] if blocks and not VOTE.search(tail[own_vote.end() if own_vote else 0:]) else []
            if block:
                for name, pat in OUTCOMES:
                    if re.search(pat, block[-1], re.I) or (name == "designated" and re.search(r"approved", block[-1], re.I)):
                        outcome, phrase, basis = name, block[-1].strip()[:200], "block statement (inferred)"
                        break
        rec = STAFF_REC.search(body)
        out.append({
            "case_no": m.case,
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
    anchors: dict[str, list[tuple[str, str]]] = {}
    for r in pd.read_csv(INPUTS / "hprb_case_anchors.csv", dtype=str).itertuples():
        anchors.setdefault(r.source_file, []).append((r.header_start, r.case_no))
    rows = []
    for slug, names in by_slug.items():
        actions = [n for n in names if n.lower().endswith(".pdf") and re.search(r"action", n, re.I)]
        sources = [(n, pdf_text(hprb_dir / "attachments" / n)) for n in actions]
        page = next((n for n in names if n.endswith(".html")), None)
        if not sources and page:
            sources = [(page, html_text(hprb_dir / "pages" / page))]
        for source, text in sources:
            date = meeting_date(slug, text)
            for it in items(text, anchors.get(source, [])):
                rows.append({"meeting_date": date, "slug": slug, "source_file": source, **it})
    df = pd.DataFrame(rows)
    df = df.drop_duplicates(["meeting_date", "case_no", "action_text"]) if len(df) else df
    return apply_review(df, hprb_dir, index)


def apply_review(df: pd.DataFrame, hprb_dir: Path, index: dict) -> pd.DataFrame:
    """Hand-read outcomes (inputs/hprb_outcome_review.csv) for actions the rules leave unclear.

    Each row's quote must appear in its source file, and each row must still match an unclear
    action, so a stale review entry stops the build instead of lingering.
    """
    review = pd.read_csv(INPUTS / "hprb_outcome_review.csv", dtype=str).fillna("")
    texts: dict[str, str] = {}
    for r in review.itertuples():
        if r.source_file not in texts:
            pdf = hprb_dir / "attachments" / r.source_file
            raw = pdf_text(pdf) if pdf.exists() else html_text(hprb_dir / "pages" / r.source_file)
            texts[r.source_file] = re.sub(r"\s+", " ", raw)
        if re.sub(r"\s+", " ", r.quote) not in texts[r.source_file]:
            raise ValueError(f"hprb_outcome_review.csv: quote not found in {r.source_file}: {r.quote[:60]!r}")
        hit = (df["source_file"] == r.source_file) & (df["case_no"] == r.case_no) & (df["outcome"] == "unclear")
        if not hit.any():
            raise ValueError(f"hprb_outcome_review.csv: no unclear action for {r.case_no} in {r.source_file}")
        df.loc[hit, ["outcome", "outcome_phrase", "outcome_basis"]] = [r.outcome, r.quote[:200], "hand review"]
    return df
