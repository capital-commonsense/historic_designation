"""Charts: one function per chart, each writing SVG, PNG and .data.csv to charts/out/.

Every chart's title states its finding (computed from the data, so it stays
true on rebuild) and its caption names the source and snapshot date.
"""

import json

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

from historic_preservation.config import CHARTS_OUT, NORMALIZED  # noqa: E402

# Okabe-Ito: distinguishable with common colour-vision deficiencies.
PALETTE = ["#0072B2", "#E69F00", "#009E73", "#CC79A7", "#56B4E9", "#D55E00", "#F0E442", "#000000"]
MUTED = "#BBBBBB"


def snapshot() -> str:
    return json.loads((NORMALIZED / "SNAPSHOT.json").read_text())["snapshot"]


def style(ax) -> None:
    ax.spines[["top", "right"]].set_visible(False)
    ax.tick_params(length=0)
    ax.grid(axis="y", color="#E5E5E5", linewidth=0.8)
    ax.set_axisbelow(True)


def save(fig, name: str, data: pd.DataFrame, caption: str) -> None:
    fig.text(0.01, 0.01, f"{caption} Snapshot {snapshot()}.", fontsize=7.5, color="#555555", wrap=True, va="bottom")
    CHARTS_OUT.mkdir(parents=True, exist_ok=True)
    for ext in ("svg", "png"):
        fig.savefig(CHARTS_OUT / f"{name}.{ext}", dpi=200, bbox_inches="tight")
    plt.close(fig)
    data.to_csv(CHARTS_OUT / f"{name}.data.csv")


def run() -> None:
    from historic_preservation.charts import comps, coverage, dcpl, lots, mayors_agent, nominations

    lots.designated_share_over_time()
    lots.value_by_designation_era()
    nominations.inventory_additions_per_year()
    nominations.nomination_outcomes()
    lots.designated_share_by_ward()
    lots.top_districts_by_value()
    dcpl.revenue_and_funds()
    mayors_agent.outcomes()
    mayors_agent.by_case_type()
    coverage.by_year()
    nominations.by_filer_type()
    nominations.by_entity_and_year()
    comps.designated_land()
    print(f"charts: wrote {CHARTS_OUT}")
