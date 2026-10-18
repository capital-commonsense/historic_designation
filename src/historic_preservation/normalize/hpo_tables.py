"""Extract HPO's "Historic Landmark Designations" table rows, as printed, from every edition.

Each annual report reprints a multi-year history (received / approved /
approved owner-opposed / denied / denied owner-opposed). Editions disagree
and printed totals don't always sum, so every row is kept with its source
edition and page; nothing is reconciled here.

Rows are rebuilt from word coordinates: each fiscal-year cell (or TOTAL) plus
the numeric cells on the same baseline to its right, within the table width.
"""

import re
from pathlib import Path

import pandas as pd
import pymupdf

YEAR = re.compile(r"^(19[89]\d|20[0-2]\d)\.?$")
CELL = re.compile(r"^[~=+<«*]*(\d+%?|-|–|—|\]|\|)[”\"’.]?$")
TABLE_WIDTH = 330  # points to the right of the year column
COLS = ["received", "approved", "approved_owner_opposed", "denied", "denied_owner_opposed"]


def _cells(words, x0, y_mid) -> list[str]:
    row = sorted((w for w in words if abs((w[1] + w[3]) / 2 - y_mid) < 3.5 and x0 < w[0] < x0 + TABLE_WIDTH),
                 key=lambda w: w[0])
    out = []
    for w in row:
        if w[4] in ("%", "(", ")"):
            continue  # some editions set "%" as its own word
        m = CELL.match(w[4])
        if not m:
            break  # ran into body text
        v = m.group(1)
        out.append("1" if v in "]|" else ("-" if v in "-–—" else v))  # OCR: ']' and '|' are '1'
    return out


def parse_cells(cells: list[str]) -> dict:
    """Layouts seen: R A AO [AO%] D DO [DO%]; percentage cells are dropped."""
    counts = [c for c in cells if not c.endswith("%")]
    if len(counts) == 5:
        return dict(zip(COLS, counts)) | {"layout": "R A AO D DO"}
    if len(cells) == 7 and not any(c.endswith("%") for c in cells):
        # FY2012-15 editions print the two percentage columns without "%" signs.
        return dict(zip(COLS, cells[:3] + cells[4:6])) | {"layout": "R A AO AO% D DO DO%"}
    return {"layout": f"unparsed ({len(counts)} counts)"}


def extract(pdf: Path, source_doc: str) -> list[dict]:
    rows = []
    doc = pymupdf.open(pdf)
    for page in doc:
        text = page.get_text()
        if not re.search(r"Owner.?\s*-?\s*Opposed", text):
            continue
        words = page.get_text("words")
        for w in words:
            label = w[4]
            if not (YEAR.match(label) or label.upper() == "TOTAL"):
                continue
            cells = _cells(words, w[2] - 1, (w[1] + w[3]) / 2)
            if len(cells) < 4:
                continue
            fy = label.upper() if label.upper() == "TOTAL" else int(label.rstrip("."))
            rows.append({"source_doc": source_doc, "page": page.number + 1, "fy": fy,
                         "printed": " ".join(cells), **parse_cells(cells)})
    return rows


def extract_all(pdfs: dict[str, Path]) -> pd.DataFrame:
    return pd.DataFrame([r for key, pdf in pdfs.items() if pdf.exists() for r in extract(pdf, key)])
