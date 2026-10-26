"""Charts: one function per chart, each writing SVG, PNG and .data.csv to charts/out/.

Each chart is drawn twice: once for the page (charts/out/) and once, narrow and tall with larger type,
for phones and newsletters (charts/out/mobile_optimized/, PNG only). In the mobile pass, `pick` chooses a
chart's phone setting, save() scales the type, fits the plot to the width, and moves legends that sit
outside the plot to a row (or rows) beneath it.

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
MOBILE_OUT = CHARTS_OUT / "mobile_optimized"
MOBILE_WIDTH = 6.0  # inches; a 375-pixel phone shows about 62 pixels an inch
MOBILE_SCALE = 1.45  # type size against the page versions
_mobile = False


def mobile() -> bool:
    return _mobile


def pick(page, phone):
    """`phone` in the mobile pass, else `page`."""
    return phone if _mobile else page


def sparse_years(years, every: int = 4) -> list[str]:
    """Tick labels for phones: every `every`th year in full, counting from the first; the rest blank."""
    first = min(years)
    return [str(y) if (y - first) % every == 0 else "" for y in years]


def title(name: str, calculated: str) -> str:
    """The headline for chart `name`: its override from TITLES if set, else the calculated one.
    Prints both, so a rebuild shows when a calculated figure has moved under an override."""
    overrides = json.loads(TITLES.read_text())
    if _mobile:  # already printed in the page pass
        return overrides.get(name) or calculated
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
    if _mobile:
        return _mobile_headline(fig, title, subtitle)
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
    if _mobile:
        _mobile_layout(fig, f"{caption} Snapshot {snapshot()}.")
        MOBILE_OUT.mkdir(parents=True, exist_ok=True)
        fig.savefig(MOBILE_OUT / f"{name}.png", dpi=240, bbox_inches="tight", pad_inches=0.2)
        plt.close(fig)
        return
    fig.text(0.01, 0.01, f"{caption} Snapshot {snapshot()}.", fontsize=7.5, color=GREY, wrap=True, va="bottom")
    CHARTS_OUT.mkdir(parents=True, exist_ok=True)
    for ext in ("svg", "png"):
        fig.savefig(CHARTS_OUT / f"{name}.{ext}", dpi=200, bbox_inches="tight", pad_inches=0.25,
                    metadata={"Date": None} if ext == "svg" else None)
    plt.close(fig)
    data.to_csv(CHARTS_OUT / f"{name}.data.csv")


# Mobile pass ---------------------------------------------------------------------------------------------

MARGIN = 0.01  # figure fraction, left and right, matching the headline's inset


def _wrap(text, width: float, renderer, along: str = "width") -> None:
    """Rewrap a Text artist's words, greedily, so no line is longer than `width` pixels (`along` "height" for
    text turned on its side). Line breaks already in the text are kept."""
    lines = []
    for paragraph in text.get_text().split("\n"):
        cur = ""
        for word in paragraph.split():
            trial = f"{cur} {word}".strip()
            text.set_text(trial)
            if cur and getattr(text.get_window_extent(renderer), along) > width:
                lines.append(cur)
                cur = word
            else:
                cur = trial
        lines.append(cur)
    text.set_text("\n".join(lines))


def _mobile_headline(fig, title: str, subtitle: str | None) -> None:
    r = fig.canvas.get_renderer()
    w, h = fig.get_size_inches()
    width = (1 - 2 * MARGIN) * w * fig.dpi
    y = 1 - 0.18 / h
    fig._headline = (title, subtitle, 17, [])
    t = fig.text(MARGIN, y, title, fontproperties=headline_font(17 * 1.25), color=INK, va="top", ha="left",
                 linespacing=1.1, parse_math=False)
    _wrap(t, width, r)
    fig._headline[3].append(t)
    bottom = fig.transFigure.inverted().transform(t.get_window_extent(r))[0][1]
    if subtitle:
        s = fig.text(MARGIN, bottom - 0.08 / h, subtitle, fontsize=10.5 * 1.25, color=GREY, va="top", ha="left")
        _wrap(s, width, r)
        fig._headline[3].append(s)
        bottom = fig.transFigure.inverted().transform(s.get_window_extent(r))[0][1]
    fig.subplots_adjust(top=bottom - 0.3 / h)


def _content(fig, r):
    """The figure-fraction box around every axes, with its tick labels, titles, texts and legends."""
    boxes = [ax.get_tightbbox(r) for ax in fig.axes if ax.get_visible()]
    x0, y0 = min(b.x0 for b in boxes), min(b.y0 for b in boxes)
    x1, y1 = max(b.x1 for b in boxes), max(b.y1 for b in boxes)
    return fig.transFigure.inverted().transform([(x0, y0), (x1, y1)]).ravel()


def _mobile_layout(fig, caption: str) -> None:
    """Scale the type, fit the axes between the headline and the margins, then add the legend row and caption."""
    from matplotlib.text import Text

    r = fig.canvas.get_renderer()
    w, h = fig.get_size_inches()
    keep = set(fig._headline[3]) if hasattr(fig, "_headline") else set()
    # A figure's only legend goes beneath the plot unless it sits above its axes; with several, those outside
    # their axes go beneath and the rest stay where the chart put them.
    alone = sum(ax.get_legend() is not None for ax in fig.axes) == 1
    below = []  # (handles, labels, title)
    for ax in fig.axes:
        leg = ax.get_legend()
        if leg is None:
            continue
        found = dict(zip(*reversed(ax.get_legend_handles_labels())))
        labels = [t.get_text() for t in leg.texts]
        handles = [found[label] for label in labels]
        title = leg.get_title().get_text() or None
        box = leg.get_bbox_to_anchor().transformed(ax.transAxes.inverted())
        leg.remove()
        if box.x0 >= 0.99 or box.y1 <= 0.01 or (alone and box.y0 < 0.99):
            below.append((handles, labels, title))
        else:
            new = ax.legend(handles, labels, loc=leg._loc, bbox_to_anchor=box, ncols=leg._ncols, mode=leg._mode,
                            fontsize=leg._fontsize * MOBILE_SCALE, title=title,
                            title_fontsize=leg.get_title().get_fontsize() * MOBILE_SCALE)
            keep.update(new.findobj(Text))
    for t in fig.findobj(Text):
        if t not in keep:
            t.set_fontsize(t.get_fontsize() * MOBILE_SCALE)
            keep.add(t)

    # Long axis labels onto more lines, no wider (or taller) than their own axes, which they sit centred on: a
    # label wider than its axes would hold the axes in from the margins. Rewrapped as the axes are fitted.
    labels = [(ax, label, label.get_text(), along) for ax in fig.axes
              for label, along in ((ax.xaxis.label, "width"), (ax.yaxis.label, "height"))]

    def wrap_labels():
        for ax, label, text, along in labels:
            label.set_text(text)
            _wrap(label, getattr(ax.get_window_extent(r), along), r, along=along)

    # Fit: the axes' outer edges (tick labels and side labels included) to the margins, their top to the headline.
    head = min((fig.transFigure.inverted().transform(a.get_window_extent(r))[0][1] for a in fig._headline[3]),
               default=1.0) if hasattr(fig, "_headline") else 1 - 0.2 / h
    for _ in range(4):
        wrap_labels()
        x0, y0, x1, y1 = _content(fig, r)
        p = fig.subplotpars
        fig.subplots_adjust(left=p.left + MARGIN - x0, right=p.right + 1 - MARGIN - x1,
                            top=p.top + head - 0.2 / h - y1, bottom=p.bottom + 0.02 - y0)
    wrap_labels()
    if hasattr(fig, "_after_layout"):
        fig._after_layout()
    low = _content(fig, r)[1]
    for t in fig.texts:  # notes a chart placed on the figure itself
        if t not in getattr(fig, "_headline", (0, 0, 0, []))[3]:
            low = min(low, fig.transFigure.inverted().transform(t.get_window_extent(r))[0][1])

    # Legend row(s): as many columns as fit across the width, spread evenly.
    width = 1 - 2 * MARGIN
    for handles, labels, title in below:
        for ncols in range(len(labels), 0, -1):
            leg = fig.legend(handles, labels, loc="upper left", bbox_to_anchor=(MARGIN, low - 0.12 / h),
                             ncols=ncols, title=title, alignment="left", fontsize=8.5 * MOBILE_SCALE,
                             title_fontsize=8.5 * MOBILE_SCALE, borderaxespad=0, columnspacing=1.2, handlelength=1.4)
            fits = leg.get_window_extent(r).width / (w * fig.dpi) <= width
            leg.remove()
            if fits or ncols == 1:
                break
        ncols = -(-len(labels) // -(-len(labels) // ncols))  # as even as the rows allow: 2 + 2, not 3 + 1
        leg = fig.legend(handles, labels, loc="upper left", bbox_to_anchor=(MARGIN, low - 0.12 / h, width, 0),
                         mode="expand", ncols=ncols, title=title, alignment="left", fontsize=8.5 * MOBILE_SCALE,
                         title_fontsize=8.5 * MOBILE_SCALE, borderaxespad=0, columnspacing=1.2, handlelength=1.4)
        low = fig.transFigure.inverted().transform(leg.get_window_extent(r))[0][1]

    c = fig.text(MARGIN, low - 0.22 / h, caption, fontsize=7.5 * 1.35, color=GREY, va="top", ha="left")
    _wrap(c, width * w * fig.dpi, r)


def run() -> None:
    global _mobile
    from historic_preservation.charts import comps, coverage, dcpl, grants, lots, mayors_agent, nominations, revenue, review_types

    charts = (lots.designated_share_over_time, lots.value_by_designation_era, nominations.inventory_additions_per_year,
              nominations.nomination_outcomes, lots.designated_share_by_ward, lots.top_districts_by_value,
              dcpl.revenue_and_funds, mayors_agent.outcomes, mayors_agent.by_case_type, mayors_agent.by_applicant,
              coverage.by_year, nominations.by_filer_type, nominations.by_entity_and_year, nominations.by_filer_success,
              comps.designated_land, comps.coverage_measures, revenue.property_tax, grants.homeowner_grants,
              review_types.review_pipeline)
    for chart in charts:
        chart()
    _mobile = True
    try:
        for chart in charts:
            chart()
    finally:
        _mobile = False
    names = {p.name.removesuffix(".data.csv") for p in CHARTS_OUT.glob("*.data.csv")} | {"comps_designated_land_video"}
    for name in sorted(set(json.loads(TITLES.read_text())) - names):
        print(f"title {name}: in {TITLES.name} but no such chart (a typo?)")
    print(f"charts: wrote {CHARTS_OUT} and {MOBILE_OUT}")
