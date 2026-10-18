"""DOB building permits (raze, demolition, new building, addition), issued 2009 onward.

The open data lists permits by issue year. There is no application date and no
record of applications that were never issued, so a raze blocked by a
designation does not appear here.
"""

import pandas as pd

from historic_preservation import addresses
from historic_preservation.config import PERMIT_LAYERS


def permits(snapshot) -> pd.DataFrame:
    from historic_preservation.normalize import attributes, epoch_ms_to_date, norm_ssl

    frames = [attributes(snapshot, layer.key) for layer in PERMIT_LAYERS
              if (snapshot / "arcgis" / layer.key / "COMPLETE.json").exists()]
    if not frames:
        return pd.DataFrame()
    df = pd.concat(frames, ignore_index=True)
    out = pd.DataFrame({
        "permit_id": df["PERMIT_ID"],
        "issued": epoch_ms_to_date(df["ISSUE_DATE"]),
        "subtype": df["PERMIT_SUBTYPE_NAME"].str.lower(),
        "status": df["APPLICATION_STATUS_NAME"].str.lower(),
        "address": df["FULL_ADDRESS"].str.replace(r",\s*WASHINGTON.*$", "", regex=True),
        "ssl": norm_ssl(df["SSL"].astype("string")),
        "ward": df["WARD"],
        "desc_of_work": df["DESC_OF_WORK"].str.strip(),
    })
    out["addr_key"] = out["address"].map(lambda a: (addresses.keys(a) or [""])[0])
    dupes = out["permit_id"].duplicated(keep=False)
    if dupes.any():
        raise ValueError(f"permits: permit ids repeated across layers: {sorted(out.loc[dupes, 'permit_id'])[:10]}")
    return out.sort_values(["issued", "permit_id"]).reset_index(drop=True)
