"""Parse the annual DC Inventory updates (HPO annual-report excerpts, FY2011+).

Each designation is laid out as a bold name, an italic address, a body
paragraph, and a smaller italic attribution such as
"Nominated by the DC Preservation League, and designated on July 26, 2018
(effective September 9, 2018)". A shared attribution ("Both nominated by ...")
applies to every preceding item that still lacks one.

Fonts and sizes vary by year (FY2011-12 are OCR'd scans with per-character
sizes), so item names are found relative to each document's dominant body
size, and the attribution is found by searching each item's full text.
"""

import re
from collections import Counter
from dataclasses import dataclass, field

import pymupdf

from historic_preservation.normalize.inventory import DATE

ATTRIBUTION = re.compile(rf"(?:[Nn]ominated by\b.*?)?\b(?:re-?)?designated\s+(?:on\s+)?{DATE}", re.S)
NOMINATOR = re.compile(r"[Nn]ominated (?:jointly |separately )?by\s+(.*?)(?:,?\s+and|;)\s+(?:re-?)?designated", re.S)
DESIGNATED = re.compile(rf"(?:re-?)?designated\s+(?:on\s+)?({DATE})")
EFFECTIVE = re.compile(rf"effective\s+(?:on\s+)?({DATE})")
SKIP_HEADINGS = re.compile(r"^(Ward \d|Historic Landmarks and Districts|Recognizing Our Heritage|National Register|Survey|.*ANNUAL REPORT.*)$", re.I)


@dataclass
class Item:
    name: str
    page: int
    address: str = ""
    body: list[str] = field(default_factory=list)
    attribution: str = ""

    def fields(self) -> dict:
        nom = NOMINATOR.search(self.attribution)
        des = DESIGNATED.search(self.attribution)
        eff = EFFECTIVE.search(self.attribution)
        return {
            "name": self.name,
            "address": self.address,
            "page": self.page,
            "nominated_by": re.sub(r"\s+", " ", nom.group(1)).strip() if nom else "",
            "designated": des.group(1) if des else "",
            "effective": eff.group(1) if eff else "",
            "attribution": self.attribution,
        }


def _lines(doc):
    for pno, page in enumerate(doc, start=1):
        for block in page.get_text("dict")["blocks"]:
            for line in block.get("lines", []):
                spans = [s for s in line["spans"] if s["text"].strip()]
                if spans:
                    text = re.sub(r"\s+", " ", "".join(s["text"] for s in line["spans"])).strip()
                    yield pno, spans, text


OCR_FIXES = ((re.compile(r"\b(\d{3}) (\d)\b"), r"\1\2"),  # "201 1" -> "2011"
             (re.compile(r"\bMorch\b"), "March"),
             (re.compile(r"(\d),(\d{4})\b"), r"\1, \2"))  # "28,2016" -> "28, 2016"


def clean_ocr(text: str) -> str:
    for pattern, repl in OCR_FIXES:
        text = pattern.sub(repl, text)
    return text


def _is_italic(spans) -> bool:
    return all("Italic" in s["font"] or "Oblique" in s["font"] for s in spans)


def parse_items(pdf_path) -> list[Item]:
    doc = pymupdf.open(pdf_path)
    lines = list(_lines(doc))
    sizes = Counter()
    for _, spans, _ in lines:
        for s in spans:
            if "Bold" not in s["font"]:
                sizes[round(s["size"])] += len(s["text"])
    body_size = sizes.most_common(1)[0][0]

    items: list[Item] = []
    for pno, spans, text in lines:
        size = max(round(s["size"]) for s in spans)
        bold = all("Bold" in s["font"] for s in spans)
        if bold and size == body_size and not SKIP_HEADINGS.match(text):
            if items and not items[-1].address and not items[-1].body:
                items[-1].name += " " + text  # name wrapped onto a second line
            else:
                items.append(Item(text, pno))
        elif items and _is_italic(spans) and not items[-1].address and not items[-1].body:
            items[-1].address = text
        elif items and not bold:
            items[-1].body.append(text)

    for i, it in enumerate(items):
        body = clean_ocr(" ".join(it.body))
        m = ATTRIBUTION.search(body)
        if not m:
            continue
        start = m.start()
        # Keep a leading "Both"/"All" so shared attributions can be spread back.
        lead = re.search(r"\b(Both|All|Each)\s+$", body[max(0, start - 6):start])
        attribution = re.sub(r"\s+", " ", (lead.group(0) if lead else "") + m.group(0)).strip()
        eff = re.match(rf"\s*(?:\((?:designation\s+)?effective\s+{DATE}\)|and effective (?:on )?{DATE})", body[m.end():])
        if eff:
            attribution += eff.group(0)
        it.attribution = attribution
        if re.match(r"(Both|All|Each)\b", attribution):
            for prev in reversed(items[:i]):
                if prev.attribution:
                    break
                prev.attribution = attribution
    return items
