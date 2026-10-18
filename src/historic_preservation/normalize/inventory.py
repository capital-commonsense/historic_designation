"""Parse the 2009 DC Inventory of Historic Sites (alphabetical PDF) into entries.

Layout rules, read from the PDF's fonts:
  - an entry starts with one or more lines set entirely in bold 11pt (its name)
  - a paragraph set entirely in italics containing ": see " is a cross-reference
    or informational note, not a designation
  - everything else is body text belonging to the current entry

Date clauses are extracted verbatim, with no interpretation; deciding which
date counts as a designation happens in the hand-curated inputs/ files.
"""

import re
from dataclasses import dataclass, field

import pymupdf

MONTH = r"(?:January|February|March|April|May|June|July|August|September|October|November|December)"
DATE = rf"{MONTH}\s+\d{{1,2}},?\s+\d{{4}}"
FURNITURE = re.compile(r"^(DISTRICT OF COLUMBIA |DC )INVENTORY OF HISTORIC SITES$|^\d+$|^[A-Z]$")

CLAUSES = {
    # Includes one entry printed as "DC June 27, 1974" with "listing" omitted.
    "dc_listing": rf"DC (?:listing\s+)?({DATE})",
    "dc_designation": rf"(?:DC designation|[Dd]esignated)\s+({DATE})",
    "effective": rf"effective\s+({DATE})",
    "expanded": rf"expanded\s+(?:DC designation\s+)?({DATE})",
    "omitted": rf"omitted from (?:the )?list\s+({DATE})",
    "nr_listing": rf"NR listing\s+({DATE})",
    "old_georgetown_act": rf"Old Georgetown Act\s+(?:of\s+)?({DATE})",
}


@dataclass
class Entry:
    name: str
    page: int  # 1-based PDF page where the entry starts
    lines: list[str] = field(default_factory=list)

    @property
    def text(self) -> str:
        return re.sub(r"\s+", " ", " ".join(self.lines)).strip()


def _line_style(line: dict) -> tuple[str, str]:
    spans = [s for s in line["spans"] if s["text"].strip()]
    text = "".join(s["text"] for s in line["spans"]).strip()
    if not spans:
        return "blank", ""
    if all("Bold" in s["font"] for s in spans) and all(round(s["size"]) == 11 for s in spans):
        return "bold", text
    if all("Italic" in s["font"] for s in spans):
        return "italic", text
    return "body", text


def paragraphs(doc: pymupdf.Document, first_page: int = 5):
    """Yield (page, [(style, text), ...]) paragraphs, skipping page furniture."""
    para, start = [], None
    for pno in range(first_page - 1, doc.page_count):
        for block in doc[pno].get_text("dict")["blocks"]:
            for line in block.get("lines", []):
                style, text = _line_style(line)
                if style != "blank" and FURNITURE.match(text):
                    continue
                if style == "blank":
                    if para:
                        yield start, para
                    para, start = [], None
                    continue
                if not para:
                    start = pno + 1
                para.append((style, text))
    if para:
        yield start, para


def parse_entries(pdf_path) -> tuple[list[Entry], list[tuple[int, str]]]:
    """Return (designation entries, cross-reference/informational lines)."""
    doc = pymupdf.open(pdf_path)
    entries: list[Entry] = []
    xrefs: list[tuple[int, str]] = []
    for page, para in paragraphs(doc):
        styles = [s for s, _ in para]
        if styles[0] == "bold":
            n = next((i for i, s in enumerate(styles) if s != "bold"), len(styles))
            name = " ".join(t for _, t in para[:n])
            entries.append(Entry(re.sub(r"\s+", " ", name).strip(), page, [t for _, t in para[n:]]))
        elif all(s == "italic" for s in styles) and ": see " in " ".join(t for _, t in para).replace("  ", " "):
            xrefs.append((page, re.sub(r"\s+", " ", " ".join(t for _, t in para))))
        elif entries:
            entries[-1].lines.extend(t for _, t in para)
    return entries, xrefs


def extract_dates(text: str) -> dict[str, str]:
    """All matches for each clause type, '; '-joined, in document order."""
    return {
        key: "; ".join(m.group(1) for m in re.finditer(pattern, text))
        for key, pattern in CLAUSES.items()
    }
