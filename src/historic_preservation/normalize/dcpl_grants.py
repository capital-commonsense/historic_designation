"""Parse DCPL grant-award PDFs into one row per listed award.

Two layouts:
  - 2015-2023: "Name of Historic Site: ... Organization: ... Funding Source:
    ... Grant Type: ... Grant Amount: $N"; year from a "(YYYY)" in the project
    title, else the nearest preceding "YYYY AWARDED/ACTIVE PROJECTS" header.
  - 2014: fund headings ("BRIGHTWOOD CAR BARN FUND"), then "APPLICANT: ...
    FUNDING AWARD: $N  PROJECT TYPE: ...".

The 2014-2016 document's first section is "2016 ACTIVE PROJECTS", which
repeats some 2015 awards, so `section` is kept and repeats are flagged rather
than dropped. Sum by year only after deciding how to treat them.
"""

import re
import subprocess
from pathlib import Path

import pandas as pd

FIELD = r"{}:\s*(.*?)\s*(?=Site Address:|Organization:|Funding Source:|Grant Type:|Grant Amount:|Approved Project|$)"
FUND_HEADING = re.compile(r"^\s*([A-Z][A-Z &’'-]+ FUND)\s*$", re.M)


def _field(block: str, name: str) -> str:
    m = re.search(FIELD.format(re.escape(name)), block, re.S)
    return re.sub(r"\s+", " ", m.group(1)).strip() if m else ""


def _labeled(flat: str, source: str) -> list[dict]:
    rows = []
    starts = [m.start() for m in re.finditer(r"Name of Historic Site:", flat)]
    for i, s in enumerate(starts):
        block = flat[s: starts[i + 1] if i + 1 < len(starts) else len(flat)]
        title_year = re.findall(r"\((20\d\d)\)", flat[max(0, s - 400): s])
        headers = re.findall(r"(20\d\d)\s*((?:A\s*W\s*A\s*R\s*D\s*E\s*D|ACTIVE)\s*P\s*R\s*O\s*J\s*E\s*C\s*T\s*S)", flat[:s], re.I)
        section = f"{headers[-1][0]} {re.sub(r'\s+', '', headers[-1][1]).lower()}" if headers else ""
        amount = re.search(r"Grant Amount:\s*\$([\d,]+)", block)
        rows.append({
            "source": source,
            "section": section,
            "year": int(title_year[-1]) if title_year else (int(headers[-1][0]) if headers else None),
            "site": _field(block, "Name of Historic Site"),
            "address": _field(block, "Site Address"),
            "organization": _field(block, "Organization"),
            "funding_source": _field(block, "Funding Source"),
            "grant_type": _field(block, "Grant Type"),
            "amount": int(amount.group(1).replace(",", "")) if amount else None,
        })
    return rows


def _fy2014(text: str, source: str) -> list[dict]:
    start = text.find("2014 Awarded Projects")
    if start < 0:
        return []
    part = text[start:]
    rows, fund = [], ""
    for m in re.finditer(r"([A-Z][A-Z &’'-]+ FUND)\s*$|APPLICANT:\s*(.+?)\s*\n\s*FUNDING AWARD:\s*\$([\d,]+)\s*\n\s*PROJECT TYPE:\s*(.+?)\s*$",
                         part, re.M):
        if m.group(1):
            fund = m.group(1).title().replace(" Fund", "")
            continue
        title = part[: m.start()].rstrip().splitlines()[-1].strip()
        rows.append({
            "source": source, "section": "2014 awarded", "year": 2014, "site": title,
            "address": "", "organization": m.group(2).strip(), "funding_source": fund,
            "grant_type": m.group(4).strip().title(), "amount": int(m.group(3).replace(",", "")),
        })
    return rows


def parse(pdf: Path, source: str) -> pd.DataFrame:
    text = subprocess.run(["pdftotext", "-layout", str(pdf), "-"], capture_output=True, text=True).stdout
    flat = re.sub(r"[ \t]+", " ", subprocess.run(["pdftotext", str(pdf), "-"], capture_output=True, text=True).stdout)
    df = pd.DataFrame(_labeled(flat, source) + _fy2014(text, source))
    key = df["organization"].str.lower() + "|" + df["amount"].astype(str)
    df["repeated_in_document"] = key.duplicated(keep=False)
    return df
