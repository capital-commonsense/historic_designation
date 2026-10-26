"""Animated comparison: designated land over time in DC, New York, Philadelphia and Boston.

House style (see charts/__init__.py): white paper, ink type, Newsreader headline, IBM Plex
Sans labels, and red for the finding only, which is DC. A row of four maps (land, Census water,
city outline) sits above the line chart of designated land share outside parkland; each city's
designations fade in in their designation year (parkland in grey) as the lines draw. Frames go to
tmp/frames/ (deletable) and ffmpeg encodes charts/out/comps_designated_land.mp4. The phone version
(portrait, the maps two by two) goes to charts/out/mobile_optimized/ as mp4 and GIF. Run with `make video`.
"""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import duckdb
import matplotlib

matplotlib.use("Agg")
import matplotlib.image as mpimg  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import matplotlib.ticker as mticker  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.collections import PathCollection  # noqa: E402
from matplotlib.font_manager import FontProperties  # noqa: E402
from matplotlib.path import Path as MPath  # noqa: E402

from historic_preservation.charts import MOBILE_OUT, _wrap, snapshot, title  # noqa: E402
from historic_preservation.config import ANALYSIS, CENSUS_PLACES, CHARTS_OUT, INPUTS, NORMALIZED, RAW  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]
FRAMES = ROOT / "tmp" / "frames"
FPS, PER_YEAR, FADE, HOLD = 30, 5, 10, 75
FIRST, LAST = 1950, pd.Timestamp.today().year
# House colors and greys (charts/__init__.py).
PAPER, INK, RED, GREY, RULE = "#FFFFFF", "#111111", "#D43D29", "#5B5B5B", "#DDDCD8"
LAND, EDGE, PARK = "#EEEDE9", "#BDBAB3", "#C4C1BA"
# Red marks the finding (DC); the other cities keep their hues, darkened to read on white.
CITIES = {"Washington": RED, "New York": "#2F6E9E", "Philadelphia": "#2E8A62", "Boston": "#B7841B"}
SHORT = {"Washington": "Washington", "New York": "New York", "Philadelphia": "Philadelphia", "Boston": "Boston"}
WATER_KEYS = {"Washington": "washington", "New York": "new_york", "Philadelphia": "philadelphia", "Boston": "boston"}


# Fonts from fonts/, registered by historic_preservation.charts.
def serif_bold(size): return FontProperties(family=["Newsreader 72pt", "DejaVu Serif"], weight="bold", size=size)  # noqa: E704
def sans(size): return FontProperties(family=["IBM Plex Sans", "DejaVu Sans"], size=size)  # noqa: E704
def sans_bold(size): return FontProperties(family=["IBM Plex Sans", "DejaVu Sans"], weight="semibold", size=size)  # noqa: E704


def _path(geojson: str) -> MPath | None:
    """A matplotlib path for a (multi)polygon, holes included."""
    g = json.loads(geojson)
    polys = [g["coordinates"]] if g["type"] == "Polygon" else g["coordinates"] if g["type"] == "MultiPolygon" else []
    rings = [np.asarray(r)[:, :2] for poly in polys for r in poly if len(r) >= 4]
    if not rings:
        return None
    return MPath.make_compound_path(*[MPath(r, closed=True) for r in rings])


def load() -> dict:
    con = duckdb.connect()
    con.install_extension("spatial")
    con.load_extension("spatial")
    to_merc = ("ST_AsGeoJSON(ST_SimplifyPreserveTopology(ST_Transform(ST_MakeValid(ST_GeomFromGeoJSON(geometry)), "
               "{crs}, 'EPSG:3857', always_xy := true), 4))")
    parks = pd.read_csv(INPUTS / "comps_parkland.csv")
    d = con.execute(f"""SELECT city, name, year, {to_merc.format(crs='crs')} AS g
                        FROM read_parquet('{NORMALIZED / 'comps.parquet'}')
                        WHERE included AND year IS NOT NULL AND geometry IS NOT NULL""").df()
    d = d[d["g"].str.contains("Polygon")]
    park = set(zip(parks["city"], parks["name"]))
    d["parkland"] = [(c, n) in park for c, n in zip(d["city"], d["name"])]
    places = con.execute(f"""SELECT geoid, {to_merc.format(crs="'EPSG:4326'")} AS g
                             FROM read_parquet('{NORMALIZED / 'comps_places.parquet'}')""").df().set_index("geoid")["g"]
    out = {}
    for city in CITIES:
        water_dir = next(RAW.glob(f"*/arcgis/comps_water_{WATER_KEYS[city]}"))
        feats = [f for p in sorted(water_dir.glob("page_*.json")) for f in json.loads(p.read_text())["features"]]
        # Land is the city boundary less Census water, so harbors (inside Boston's and New York's
        # limits) are neither drawn nor counted in each map's extent; slivers under 0.05 km² are dropped.
        land = con.execute("""
            WITH w AS (SELECT ST_Union_Agg(ST_MakeValid(ST_Transform(ST_GeomFromGeoJSON(g), 'EPSG:4326', 'EPSG:3857',
                                                                     always_xy := true))) AS geom
                       FROM (SELECT unnest(?) AS g)),
                 parts AS (SELECT unnest(ST_Dump(ST_Difference(ST_GeomFromGeoJSON(?), w.geom))).geom AS geom FROM w)
            SELECT ST_AsGeoJSON(ST_Collect(list(geom))) FROM parts WHERE ST_Area(geom) > 50000""",
                           [[json.dumps(f["geometry"]) for f in feats if f.get("geometry")],
                            places[CENSUS_PLACES[city]]]).fetchone()[0]
        out[city] = {"land": _path(land), "designations": d[d["city"] == city]}
    return out


def render(preview: list[int] | None = None, mobile: bool = False) -> Path:
    """All frames and the mp4; or, with preview, only those frame numbers (no video). `mobile`: the portrait
    version for phones (charts/out/mobile_optimized/, with a GIF), the maps in a 2x2 grid above the chart."""
    data = load()
    series = pd.read_csv(ANALYSIS / "comps_by_year.csv").pivot(
        index="year", columns="city", values="designated_area_share_excl_parkland")[list(CITIES)]
    ymax = float(series.max().max()) * 1.12
    final = series.iloc[-1]
    others = final.drop("Washington")
    headline = title("comps_designated_land_video",
                     f"DC has designated {final['Washington']:.0%} of its land as historic. "
                     f"Its peers: {others.min():.0%}\u2013{others.max():.0%}")
    subtitle = f"Share of city land inside historic districts and landmarks, excluding parkland, {FIRST}\u2013{LAST}"
    sources = (f"Grey on the maps: parkland, left out of the lines. Today's boundaries, dated by designation.\n"
               f"Sources: DC GIS; NYC Open Data (LPC); City of Philadelphia; City of Boston; Census TIGERweb; "
               f"snapshot {snapshot()}")

    if mobile:
        # 1080 x 1680: the extra height over 1500 all goes to the maps, which are tall rather than wide.
        fig = plt.figure(figsize=(10.8, 16.8), dpi=100, facecolor=PAPER)
        L, R = 0.06, 0.94
        k = 15 / 16.8  # fixed-height spacings below were set on a 1500-pixel frame
        r = fig.canvas.get_renderer()
        width = (R - L) * 1080
        head = fig.text(L, 1 - 0.035 * k, headline, color=INK, fontproperties=serif_bold(46), va="top", linespacing=1.05)
        _wrap(head, width, r)
        y = fig.transFigure.inverted().transform(head.get_window_extent(r))[0][1] - 0.012 * k
        sub = fig.text(L, y, subtitle, color=GREY, fontproperties=sans(23), va="top", linespacing=1.3)
        _wrap(sub, width, r)
        y = fig.transFigure.inverted().transform(sub.get_window_extent(r))[0][1]
        # Maps: two rows of two below the headline; the city name over each slot's left edge.
        label_h, gap_x, gap_y, bottom = 0.027 * k, 0.04, 0.02 * k, 0.36 * k
        slot_w = (R - L - gap_x) / 2
        slot_h = (y - 0.025 * k - bottom - gap_y) / 2 - label_h
        slots = [(L + (k % 2) * (slot_w + gap_x), bottom + (1 - k // 2) * (slot_h + label_h + gap_y), slot_w, slot_h)
                 for k in range(4)]
        city_font, anchor = sans_bold(24), "W"
    else:
        fig = plt.figure(figsize=(19.2, 10.8), dpi=100, facecolor=PAPER)
        L, R = 0.055, 0.945  # text and graphics share these margins
        fig.text(L, 0.925, headline, color=INK, fontproperties=serif_bold(40), va="baseline")
        fig.text(L, 0.878, subtitle, color=GREY, fontproperties=sans(17), va="baseline")
        # Maps: a row of four, each fitted to its slot; the city name sits on the slot's left edge.
        slot_w, gap, top, bottom = (R - L - 3 * 0.02) / 4, 0.02, 0.785, 0.43
        slots = [(L + k * (slot_w + gap), bottom, slot_w, top - bottom) for k in range(4)]
        city_font, anchor, label_h = sans_bold(15), "NW", 0.012

    groups = []  # (collection, year)
    for (x0, y0, w_, h_), city in zip(slots, CITIES):
        fig.text(x0, y0 + h_ + label_h * (0.25 if mobile else 1), SHORT[city].upper(), color=CITIES[city],
                 fontproperties=city_font)
        ax = fig.add_axes([x0, y0, w_, h_], facecolor=PAPER)
        ax.set_axis_off()
        b = data[city]["land"]
        ext = b.get_extents()
        pad = 0.02 * max(ext.width, ext.height)
        ax.add_collection(PathCollection([b], facecolor=LAND, edgecolor=EDGE, linewidth=0.6, zorder=1))
        for (year, park), g in data[city]["designations"].groupby(["year", "parkland"]):
            paths = [p for p in map(_path, g["g"]) if p is not None]
            col = PathCollection(paths, facecolor=PARK if park else CITIES[city], edgecolor="none", alpha=0, zorder=3)
            ax.add_collection(col)
            groups.append((col, int(year)))
        ax.set_xlim(ext.x0 - pad, ext.x1 + pad)
        ax.set_ylim(ext.y0 - pad, ext.y1 + pad)
        ax.set_aspect("equal", adjustable="box", anchor=anchor)

    # Chart: light rules, grey ticks, no spines, labelled endpoints (on phones, the share alone: the colors
    # match the city names over the maps).
    chart = fig.add_axes([L + 0.08, 0.14 * k, R - L - 0.08 - 0.115, 0.175 * k] if mobile else
                         [L + 0.03, 0.135, R - L - 0.03 - 0.125, 0.235], facecolor=PAPER)
    chart.set_xlim(FIRST, LAST)
    chart.set_ylim(0, ymax)
    chart.yaxis.set_major_locator(mticker.MultipleLocator(0.05))
    chart.yaxis.set_major_formatter(mticker.PercentFormatter(1.0, decimals=0))
    chart.xaxis.set_major_locator(mticker.MultipleLocator(20 if mobile else 10))
    for s_ in chart.spines.values():
        s_.set_visible(False)
    chart.tick_params(colors=GREY, length=0, pad=10)
    for t in chart.get_xticklabels() + chart.get_yticklabels():
        t.set_fontproperties(sans(21 if mobile else 14))
    chart.grid(axis="y", color=RULE, linewidth=1.3)
    chart.set_axisbelow(True)
    lines, dots, ends = {}, {}, {}
    for c, col in CITIES.items():
        dc = c == "Washington"
        lines[c] = chart.plot([], [], color=col, lw=(5.5 if dc else 3.4) if mobile else (4.5 if dc else 2.6),
                              drawstyle="steps-post", solid_joinstyle="miter", zorder=4 if dc else 3)[0]
        dots[c] = chart.plot([], [], "o", color=col, ms=(11 if dc else 8) if mobile else (9 if dc else 6), zorder=5)[0]
        ends[c] = chart.text(0, 0, "", color=col, va="center", zorder=5,
                             fontproperties=sans_bold((26 if dc else 21) if mobile else (19 if dc else 14)))
    if mobile:  # inside the chart's empty top left
        year_text = chart.text(0.02, 1.0, "", transform=chart.transAxes, color=INK, fontproperties=serif_bold(50),
                               va="top", ha="left")
    else:
        year_text = fig.text(R, chart.get_position().y1 + 0.03, "", color=INK, fontproperties=serif_bold(44),
                             va="bottom", ha="right")
    if mobile:
        foot = fig.text(L, 0.02 * k, sources.replace("\n", " "), color=GREY, fontproperties=sans(16), va="bottom",
                        linespacing=1.4)
        _wrap(foot, width, r)
    else:
        fig.text(L, 0.035, sources, color=GREY, fontproperties=sans(12.5), va="baseline", linespacing=1.5)
    # Optional wordmark, bottom right, from a local checkout of the brand kit named by $HP_BRAND_DIR.
    brand = os.environ.get("HP_BRAND_DIR")
    wm = Path(brand) / "Capital_Commonsense_Wordmark_Transparent_4096.png" if brand else None
    if wm and wm.exists() and not mobile:
        img = mpimg.imread(wm)
        h = 0.026  # figure height fraction
        w = h * img.shape[1] / img.shape[0] * 1080 / 1920
        wax = fig.add_axes([R - w, 0.026, w, h])
        wax.imshow(img)
        wax.set_axis_off()

    frames = FRAMES.with_name("frames_mobile") if mobile else FRAMES
    if frames.exists():
        shutil.rmtree(frames)
    frames.mkdir(parents=True)
    n_frames = (LAST - FIRST + 1) * PER_YEAR + HOLD
    for i in (preview if preview is not None else range(n_frames)):
        t = min(FIRST + i / PER_YEAR, LAST + 0.999)
        for col, year in groups:
            age = (t - year) * PER_YEAR  # frames since the designation year began
            col.set_alpha(0.0 if age < 0 else 0.9 * min(1.0, age / FADE))
        yr = int(t)
        tx = min(t, LAST)
        for c, line in lines.items():
            s_ = series[c].loc[:yr]
            xs = list(s_.index) + [tx]
            ys = list(s_.values) + [s_.values[-1]]
            line.set_data(xs, ys)
            dots[c].set_data([tx], [ys[-1]])
            ends[c].set_text(f"{ys[-1]:.1%}" if mobile else f"{SHORT[c]} {ys[-1]:.1%}")
        # End labels: keep a small gap between cities' values.
        gap_y, placed = ymax * (0.13 if mobile else 0.075), []
        for c in sorted(lines, key=lambda c: lines[c].get_ydata()[-1]):
            y = lines[c].get_ydata()[-1]
            y = max([y] + [p + gap_y for p in placed])
            placed.append(y)
            ends[c].set_position((tx + (1.5 if mobile else 0.8), y))
        year_text.set_text(str(yr))
        fig.savefig(frames / f"f{i:05d}.png", facecolor=PAPER)
    plt.close(fig)
    if preview is not None:
        return frames

    out_dir = MOBILE_OUT if mobile else CHARTS_OUT
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / "comps_designated_land.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(FPS), "-i", str(frames / "f%05d.png"),
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", "-movflags", "+faststart", str(out)],
                   check=True)
    if mobile:  # a GIF too, for newsletter tools that take no video: 10 frames a second, 720 pixels wide
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(FPS), "-i", str(frames / "f%05d.png"),
                        "-vf", "fps=10,scale=720:-1:flags=lanczos,split[a][b];[a]palettegen=stats_mode=diff[p];"
                               "[b][p]paletteuse=dither=bayer:bayer_scale=4", str(out.with_suffix(".gif"))], check=True)
    return out


if __name__ == "__main__":
    # python -m historic_preservation.charts.comps_video [page|mobile|all]
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    for m in {"page": [False], "mobile": [True], "all": [False, True]}[which]:
        print(render(mobile=m))
