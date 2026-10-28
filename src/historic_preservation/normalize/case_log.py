"""Parse HPO's "Record of HPRB Actions on Designation Applications" (the case log), released under FOIA.

One line per designation case: property, case number (YY-NN, YY the fiscal year the case was opened) and
the board's action with its date, e.g. "Barney Circle Historic District<TAB>08-01<TAB>Withdrawn March 14,
2025". Cases with no action yet have an empty action column. The layout is loose:
  - a few National Register framework documents have no case number;
  - one name wraps onto a second line ("National Association for the Relief of Destitute / Colored Women
    and Children");
  - a case number can follow the name without a tab, and a name can end in a stray column ("amendment<TAB>2");
  - some actions carry two dates ("Denied May 23, 2019 and February 23, 2023"); the last is kept as the
    action date, and the full text stays in `action_raw`.

The Word file is read through a plain-text export: macOS `textutil`, or LibreOffice's `soffice`.
"""

import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import pandas as pd

CASE = re.compile(r"(?<![\d-])(\d{2})-(\d{2})(?![\d-])")
MONTHS = "January|February|March|April|May|June|July|August|September|October|November|December"
MON = "Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec"
DAY_DATE = re.compile(rf"\b((?:{MONTHS})|(?:{MON})\.?)\s+(\d{{1,2}}),\s+((?:19|20)\d{{2}})")
MONTH_DATE = re.compile(rf"\b({MONTHS})\s+((?:19|20)\d{{2}})")
YEAR_ONLY = re.compile(r"\b(?:early |late )?((?:19|20)\d{2})\b")
FISCAL_YEAR = re.compile(r"\bFY((?:19|20)\d{2})\b")
# Header and footer lines of the document, not cases.
FURNITURE = re.compile(r"^(RECORD OF HPRB ACTIONS|Property\s+Case Number|PAGE \d+|GOVERNMENT OF THE DISTRICT"
                       r"|HISTORIC PRESERVATION REVIEW BOARD|Office of the Director|\d+ North Capitol Street)")
# First word(s) of the action column -> one action vocabulary.
ACTIONS = (
    (r"designated", "designated"), (r"amended", "amended"), (r"adopted", "adopted"), (r"denied", "denied"),
    (r"withdrawn", "withdrawn"), (r"superseded", "superseded"), (r"revoked", "revoked"),
    (r"continued", "continued"), (r"listed", "listed"), (r"forwarded|doe only", "forwarded"),
    (r"1964 listing updated", "updated"),
)


def text(path: Path) -> str:
    """The document as plain text, tabs kept between columns."""
    if shutil.which("textutil"):
        return subprocess.run(["textutil", "-convert", "txt", "-stdout", str(path)], check=True,
                              capture_output=True, text=True).stdout
    if shutil.which("soffice"):
        with tempfile.TemporaryDirectory() as tmp:
            subprocess.run(["soffice", "--headless", "--convert-to", "txt:Text", "--outdir", tmp, str(path)],
                           check=True, capture_output=True)
            return (Path(tmp) / f"{path.stem}.txt").read_text()
    raise RuntimeError(f"reading {path.name} needs macOS textutil or LibreOffice (soffice)")


def action(raw: str) -> str:
    if not raw:
        return "none"  # no action recorded: pending, or never heard
    for pattern, name in ACTIONS:
        if re.match(pattern, raw, re.I):
            return name
    raise ValueError(f"case log: unrecognized action {raw!r}")


def action_date(raw: str) -> tuple[pd.Timestamp | None, str]:
    """The last date in the action text, and its precision (day, month, year, fy or none). A fiscal year
    alone ("Forwarded FY2020") gives no date."""
    if days := DAY_DATE.findall(raw):
        mon, day, year = days[-1]
        return pd.to_datetime(f"{mon[:3]} {day} {year}", format="%b %d %Y"), "day"
    if months := MONTH_DATE.findall(raw):
        mon, year = months[-1]
        return pd.to_datetime(f"{mon} 1 {year}", format="%B %d %Y"), "month"
    if FISCAL_YEAR.search(raw):
        return None, "fy"
    if years := YEAR_ONLY.findall(raw):
        return pd.Timestamp(int(years[-1]), 1, 1), "year"
    return None, "none"


def parse(doc: str) -> pd.DataFrame:
    rows, carry = [], ""
    for line_no, line in enumerate(doc.splitlines(), start=1):
        stripped = line.strip()
        if not stripped or FURNITURE.match(stripped):
            continue
        cells = [c.strip() for c in line.split("\t") if c.strip()]
        m = CASE.search(line)
        if m is None and len(cells) == 1:
            carry = f"{carry} {stripped}".strip()  # a name wrapped onto the next line
            continue
        if m:
            name = line[:m.start()].strip()
            rest = line[m.end():].strip()
            case_no = f"{m.group(1)}-{m.group(2)}"
            year = int(m.group(1))
        else:  # a framework document with no case number: name<TAB><TAB>action
            name, rest, case_no, year = cells[0], " ".join(cells[1:]), "", None
        name = re.sub(r"\s+", " ", f"{carry} {name}".replace("\t", " ")).strip()
        carry = ""
        rest = re.sub(r"\s+", " ", rest)
        date, precision = action_date(rest)
        superseded = re.search(r"Superseded by (?:case |#)?(\d{2}-\d{2})", rest)
        rows.append({
            "case_no": case_no,
            "case_fy": (2000 + year if year < 50 else 1900 + year) if year is not None else pd.NA,
            "name": name,
            "action": action(rest),
            "action_date": date,
            "date_precision": precision,
            "superseded_by": superseded.group(1) if superseded else "",
            "action_raw": rest,
            "line": line_no,
        })
    if carry:
        raise ValueError(f"case log: dangling line {carry!r}")
    out = pd.DataFrame(rows)
    numbered = out[out["case_no"] != ""]
    dupes = numbered[numbered["case_no"].duplicated(keep=False)]
    if len(dupes):
        raise ValueError(f"case log: repeated case numbers {sorted(set(dupes['case_no']))}")
    out["case_fy"] = out["case_fy"].astype("Int64")
    return out


def case_log(folder: Path) -> pd.DataFrame:
    """Every case log release in `folder` (one dated subfolder per release); the newest wins per case."""
    parts = []
    for doc in sorted(folder.glob("*/*.doc")):
        part = parse(text(doc))
        parts.append(part.assign(release=doc.parent.name, source_doc=f"{doc.parent.name}/{doc.name}"))
    if not parts:
        return pd.DataFrame()
    out = pd.concat(parts, ignore_index=True)
    numbered = out["case_no"] != ""
    newest = out[numbered].drop_duplicates("case_no", keep="last")
    return pd.concat([newest, out[~numbered]], ignore_index=True)
