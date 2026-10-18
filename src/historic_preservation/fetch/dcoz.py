"""Zoning Commission case exhibit lists from the DC Office of Zoning (app.dcoz.dc.gov).

Each case's exhibit report lists every exhibit with its number, title, page
count and filing date. Zoning Commission case numbers are "YY-NN"; for each
year, cases are tried in order until several in a row return no exhibits.
"""

import json
import re
from pathlib import Path

import httpx

from historic_preservation.fetch.http import PoliteClient

REPORT = "https://app.dcoz.dc.gov/CaseReport/ViewExhibitsReport.aspx"
MAX_MISSES = 6


def _has_exhibits(html: str) -> bool:
    return bool(re.search(r"\d{2}/\d{2}/\d{4}", html))


def fetch_zc_cases(client: PoliteClient, dest: Path, years: range) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    index_path = dest / "index.json"
    index = json.loads(index_path.read_text()) if index_path.exists() else {"cases": {}, "years_done": []}
    for year in years:
        yy = f"{year % 100:02d}"
        if yy in index["years_done"]:
            continue
        misses, n = 0, 1
        while misses < MAX_MISSES:
            case = f"{yy}-{n:02d}"
            path = dest / f"zc_{case}.html"
            if case not in index["cases"]:
                try:
                    html = client.get(REPORT, {"case_id": case}).text
                except httpx.HTTPError as e:
                    index["cases"][case] = {"status": f"error: {e}"}
                    html = ""
                else:
                    found = _has_exhibits(html)
                    if found:
                        path.write_text(html)
                    index["cases"][case] = {"exhibits": found}
                index_path.write_text(json.dumps(index, indent=1))
            misses = 0 if index["cases"][case].get("exhibits") else misses + 1
            n += 1
        index["years_done"].append(yy)
        index_path.write_text(json.dumps(index, indent=1))
    found = sum(1 for c in index["cases"].values() if c.get("exhibits"))
    print(f"  dcoz: {found} Zoning Commission cases with exhibits")
