"""Charts: one function per chart, each writing SVG, PNG and .data.csv to charts/out/.

Every chart's headline states its finding (computed from the data, so it stays
true on rebuild) and its caption names the source and snapshot date. House style below.
A hand-written headline in inputs/chart_titles.json (chart name -> text, null for the computed one)
replaces the computed headline; each build prints both so a shifted figure shows up.
"""

import json
import textwrap

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib import font_manager  # noqa: E402

from historic_preservation.config import CHARTS_OUT, INPUTS, NORMALIZED, ROOT  # noqa: E402

# House style: ink type on white, Newsreader Bold headlines, IBM Plex Sans for everything else,
# light rules, and red for the finding only (at most once a chart).
INK, RED, PAPER = "#111111", "#D43D29", "#FFFFFF"
GREY, RULE = "#5B5B5B", "#DDDCD8"  # secondary text; gridlines
DARK, MID, LIGHT = "#6E6B66", "#A9A6A0", "#D3D0CA"  # context series, darkest first
# Hues for categories that greys can't separate; the same blue, green and gold as the city comparison.
BLUE, GREEN, GOLD = "#2F6E9E", "#2E8A62", "#B7841B"
MUTED = LIGHT

# Fonts ship in fonts/ (SIL Open Font License; see the license files there).
for _f in (ROOT / "fonts").glob("*.ttf"):
    font_manager.fontManager.addfont(str(_f))
_HEADLINE_FAMILIES = ["Newsreader 72pt", "DejaVu Serif"]


def headline_font(size: float) -> font_manager.FontProperties:
    return font_manager.FontProperties(family=_HEADLINE_FAMILIES, weight="bold", size=size)


plt.rcParams.update({
    "font.family": ["IBM Plex Sans", "DejaVu Sans"], "font.size": 9.5,
    "text.color": INK, "axes.labelcolor": GREY, "xtick.color": GREY, "ytick.color": GREY,
    "axes.edgecolor": RULE, "axes.facecolor": PAPER, "figure.facecolor": PAPER,
    "axes.titlecolor": INK, "axes.titleweight": "semibold", "axes.titlesize": 10,
    "legend.frameon": False, "legend.fontsize": 8.5, "hatch.color": MID, "hatch.linewidth": 0.6,
    "svg.hashsalt": "historic-preservation",  # stable SVG ids, so a rebuild from the same data is identical
})


TITLES = INPUTS / "chart_titles.json"


def title(name: str, calculated: str) -> str:
    """The headline for chart `name`: its override from TITLES if set, else the calculated one.
    Prints both, so a rebuild shows when a calculated figure has moved under an override."""
    overrides = json.loads(TITLES.read_text())
    if name not in overrides:
        print(f"title {name}: not in {TITLES.name}; add it (null keeps the calculated headline)")
    override = overrides.get(name)
    print(f"title {name}\n  calculated: {calculated}" + (f"\n  override:   {override}" if override else ""))
    return override or calculated


def snapshot() -> str:
    return json.loads((NORMALIZED / "SNAPSHOT.json").read_text())["snapshot"]


def style(ax, grid: str = "y") -> None:
    """Chart treatment: no spines, no tick marks, light rules along one axis."""
    for s in ax.spines.values():
        s.set_visible(False)
    ax.tick_params(length=0, pad=6)
    ax.grid(axis=grid, color=RULE, linewidth=1)
    ax.grid(axis="y" if grid == "x" else "x", visible=False)
    ax.set_axisbelow(True)


def headline(fig, title: str, subtitle: str | None = None, size: float = 17) -> None:
    """A Newsreader headline (the chart's finding) and an optional unit/period line, top left,
    wrapped to the figure's width; moves the plot area down to make room."""
    w, h = fig.get_size_inches()
    lines = textwrap.wrap(title, int(w * 72 / (size * 0.5)))
    if len(lines) > 1:  # balance the lines rather than leave a word or two on the last
        lines = textwrap.wrap(title, -(-len(title) // len(lines)) + 6)
    y = 1 - 0.18 / h
    fig._headline = (title, subtitle, size, [])  # save() swaps in an override and redraws
    fig._headline[3].append(fig.text(0.01, y, "\n".join(lines), fontproperties=headline_font(size),
             color=INK, va="top", ha="left", linespacing=1.1, parse_math=False))
    used = len(lines) * size * 1.2 / 72
    if subtitle:
        fig._headline[3].append(fig.text(0.01, y - used / h - 0.06 / h, subtitle, fontsize=10.5, color=GREY,
                                         va="top", ha="left"))
        used += 0.3
    fig.subplots_adjust(top=y - (used + 0.3) / h)


def save(fig, name: str, data: pd.DataFrame, caption: str) -> None:
    if hasattr(fig, "_headline"):
        calculated, subtitle, size, artists = fig._headline
        final = title(name, calculated)
        if final != calculated:
            for a in artists:
                a.remove()
            headline(fig, final, subtitle, size)
    fig.text(0.01, 0.01, f"{caption} Snapshot {snapshot()}.", fontsize=7.5, color=GREY, wrap=True, va="bottom")
    CHARTS_OUT.mkdir(parents=True, exist_ok=True)
    for ext in ("svg", "png"):
        fig.savefig(CHARTS_OUT / f"{name}.{ext}", dpi=200, bbox_inches="tight", pad_inches=0.25,
                    metadata={"Date": None} if ext == "svg" else None)
    plt.close(fig)
    data.to_csv(CHARTS_OUT / f"{name}.data.csv")


def run() -> None:
    from historic_preservation.charts import comps, coverage, dcpl, grants, lots, mayors_agent, nominations, revenue, review_types

    lots.designated_share_over_time()
    lots.value_by_designation_era()
    nominations.inventory_additions_per_year()
    nominations.nomination_outcomes()
    lots.designated_share_by_ward()
    lots.top_districts_by_value()
    dcpl.revenue_and_funds()
    mayors_agent.outcomes()
    mayors_agent.by_case_type()
    mayors_agent.by_applicant()
    coverage.by_year()
    nominations.by_filer_type()
    nominations.by_entity_and_year()
    nominations.by_filer_success()
    comps.designated_land()
    comps.coverage_measures()
    revenue.property_tax()
    grants.homeowner_grants()
    review_types.review_pipeline()
    charts = {p.name.removesuffix(".data.csv") for p in CHARTS_OUT.glob("*.data.csv")} | {"comps_designated_land_video"}
    for name in sorted(set(json.loads(TITLES.read_text())) - charts):
        print(f"title {name}: in {TITLES.name} but no such chart (a typo?)")
    print(f"charts: wrote {CHARTS_OUT}")
