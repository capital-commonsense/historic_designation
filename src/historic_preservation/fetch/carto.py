"""Page a Carto SQL query (Philadelphia's open data server) into a raw snapshot as CSV pages."""

import json
from datetime import datetime, timezone
from pathlib import Path

from historic_preservation.fetch.http import PoliteClient

PAGE = 50_000


def fetch_query(client: PoliteClient, key: str, base: str, sql: str, dest: Path, order: str = "objectid") -> None:
    out = dest / key
    if (out / "COMPLETE.json").exists():
        print(f"  {key}: already complete, skipping")
        return
    out.mkdir(parents=True, exist_ok=True)
    stats = client.get_json(base, {"q": f"SELECT count(*) AS n, max({order}) AS hi FROM ({sql}) q"})["rows"][0]
    count, hi = stats["n"], stats["hi"]
    rows = 0
    # Pages are id ranges (ids_<lo>.csv holds lo < id <= lo + PAGE): OFFSET paging times out on this server.
    for lo in range(0, hi, PAGE):
        page = out / f"ids_{lo:07d}.csv"
        if not page.exists():
            q = f"SELECT * FROM ({sql}) q WHERE {order} > {lo} AND {order} <= {lo + PAGE} ORDER BY {order}"
            text = client.get(base, {"q": q, "format": "csv"}).text
            page.with_suffix(".tmp").write_text(text)
            page.with_suffix(".tmp").rename(page)
        rows += page.read_text().count("\n") - 1
        print(f"  {key}: {rows:,}/{count:,}", end="\r")
    print()
    if rows != count:
        raise RuntimeError(f"{key}: fetched {rows} rows, server count {count}")
    (out / "COMPLETE.json").write_text(json.dumps({
        "url": base, "sql": sql, "server_count": count, "rows": rows,
        "completed_at": datetime.now(timezone.utc).isoformat()}))
