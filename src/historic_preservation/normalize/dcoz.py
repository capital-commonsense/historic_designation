"""Parse Zoning Commission exhibit lists and flag preservation-related exhibits.

Flags are keyword matches on exhibit titles only (the PDFs aren't read here),
so a flag means "look at this exhibit", not "this is an agreement".
"""

import html as htmllib
import json
import re
from pathlib import Path

import pandas as pd

EXHIBIT_URL = "https://app.dcoz.dc.gov/CaseReport/ViewExhibit.aspx?exhibitId={}"
FLAGS = {
    "dcpl": r"preservation league|\bDCPL\b|don.t tear it down",
    "committee_of_100": r"committee of 100",
    "landmark_or_designation": r"landmark|designat|historic district",
    "withdrawal": r"withdr[ae]w",
    "agreement": r"agreement|memorandum of understanding|\bMOU\b|covenant",
    "mitigation": r"mitigat",
    "not_oppose": r"not (?:to )?oppose|non-?opposition",
    "hprb_hpo": r"\bHPRB\b|\bHPO\b|historic preservation (?:review board|office)",
}


def parse_case(path: Path, case: str) -> list[dict]:
    t = path.read_text(errors="ignore")
    rows = []
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", t, re.S):
        cells = [htmllib.unescape(re.sub(r"<[^>]+>", "", c)).strip() for c in re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)]
        if len(cells) < 7 or not re.match(r"\d{2}/\d{2}/\d{4}$", cells[6]):
            continue
        link = re.search(r"exhibitId=(\d+)", tr)
        title = re.sub(r"\s+", " ", cells[4])
        rows.append({
            "case_type": "ZC", "case_no": case, "exhibit_no": cells[3], "title": title,
            "pages": cells[5], "date": pd.to_datetime(cells[6], format="%m/%d/%Y").date(),
            "url": EXHIBIT_URL.format(link.group(1)) if link else "",
            **{f"flag_{k}": bool(re.search(p, title, re.I)) for k, p in FLAGS.items()},
        })
    return rows


def exhibits(dcoz_dir: Path) -> pd.DataFrame:
    index = json.loads((dcoz_dir / "index.json").read_text())
    rows = []
    for case, info in sorted(index["cases"].items()):
        if info.get("exhibits"):
            rows += parse_case(dcoz_dir / f"zc_{case}.html", case)
    return pd.DataFrame(rows)
