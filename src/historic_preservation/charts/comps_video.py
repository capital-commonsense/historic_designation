"""Animated comparison: designated land over time in DC, New York, Philadelphia and Boston.

Capital Commonsense house style (brand_kit/): white paper, ink type, Newsreader headline, IBM Plex
Sans labels, and red for the finding only, which is DC. A row of four maps (land, Census water,
city outline) sits above the line chart of designated land share outside parkland; each city's
designations fade in in their designation year (parkland in grey) as the lines draw. Frames go to
tmp/frames/ (deletable) and ffmpeg encodes charts/out/comps_designated_land.mp4. Run with `make video`.
"""

import json
import shutil
import subprocess
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

from historic_preservation.charts import snapshot, title  # noqa: E402
from historic_preservation.config import ANALYSIS, CENSUS_PLACES, CHARTS_OUT, INPUTS, NORMALIZED, RAW  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]
FRAMES = ROOT / "tmp" / "frames"
BRAND = ROOT / "brand_kit"
FPS, PER_YEAR, FADE, HOLD = 30, 5, 10, 75
FIRST, LAST = 1950, pd.Timestamp.today().year
# House colors (brand_kit/Capital_Commonsense_Kit_README.md) and the chart example's greys.
PAPER, INK, RED, GREY, RULE = "#FFFFFF", "#111111", "#D43D29", "#5B5B5B", "#DDDCD8"
LAND, EDGE, PARK = "#EEEDE9", "#BDBAB3", "#C4C1BA"
# Red marks the finding (DC); the other cities keep their hues, darkened to read on white.
CITIES = {"Washington": RED, "New York": "#2F6E9E", "Philadelphia": "#2E8A62", "Boston": "#B7841B"}
SHORT = {"Washington": "Washington", "New York": "New York", "Philadelphia": "Philadelphia", "Boston": "Boston"}
WATER_KEYS = {"Washington": "washington", "New York": "new_york", "Philadelphia": "philadelphia", "Boston": "boston"}


def _font(name: str, size: float) -> FontProperties:
    path = BRAND / "fonts" / name
    if path.exists():
        return FontProperties(fname=path, size=size)
    # brand_kit/ is not in the public repo: fall back to matplotlib's own fonts
    return FontProperties(family="serif" if name.startswith("Newsreader") else "sans-serif",
                          weight="bold" if "Bold" in name else "normal", size=size)


def serif_bold(size): return _font("Newsreader72pt-Bold.ttf", size)  # noqa: E704
def sans(size): return _font("IBMPlexSans-Regular.ttf", size)  # noqa: E704
def sans_bold(size): return _font("IBMPlexSans-SemiBold.ttf", size)  # noqa: E704


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


def render(preview: list[int] | None = None) -> Path:
    """All frames and the mp4; or, with preview, only those frame numbers (no video)."""
    data = load()
    series = pd.read_csv(ANALYSIS / "comps_by_year.csv").pivot(
        index="year", columns="city", values="designated_area_share_excl_parkland")[list(CITIES)]
    ymax = float(series.max().max()) * 1.12
    final = series.iloc[-1]
    others = final.drop("Washington")

    fig = plt.figure(figsize=(19.2, 10.8), dpi=100, facecolor=PAPER)
    L, R = 0.055, 0.945  # text and graphics share these margins
    fig.text(L, 0.925, title("comps_designated_land_video",
                             f"DC has designated {final['Washington']:.0%} of its land as historic. "
                             f"Its peers: {others.min():.0%}\u2013{others.max():.0%}"),
             color=INK, fontproperties=serif_bold(40), va="baseline")
    fig.text(L, 0.878, f"Share of city land inside historic districts and landmarks, excluding parkland, {FIRST}\u2013{LAST}",
             color=GREY, fontproperties=sans(17), va="baseline")

    # Maps: a row of four, each fitted to its slot; the city name sits on the slot's left edge.
    groups = []  # (collection, year)
    slot_w, gap, top, bottom = (R - L - 3 * 0.02) / 4, 0.02, 0.785, 0.43
    for k, city in enumerate(CITIES):
        x0 = L + k * (slot_w + gap)
        fig.text(x0, top + 0.012, SHORT[city].upper(), color=CITIES[city], fontproperties=sans_bold(15))
        ax = fig.add_axes([x0, bottom, slot_w, top - bottom], facecolor=PAPER)
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
        ax.set_aspect("equal", adjustable="box", anchor="NW")

    # Chart: the brand example's treatment (light rules, grey ticks, no spines, labelled endpoints).
    chart = fig.add_axes([L + 0.03, 0.135, R - L - 0.03 - 0.125, 0.235], facecolor=PAPER)
    chart.set_xlim(FIRST, LAST)
    chart.set_ylim(0, ymax)
    chart.yaxis.set_major_locator(mticker.MultipleLocator(0.05))
    chart.yaxis.set_major_formatter(mticker.PercentFormatter(1.0, decimals=0))
    chart.xaxis.set_major_locator(mticker.MultipleLocator(10))
    for s_ in chart.spines.values():
        s_.set_visible(False)
    chart.tick_params(colors=GREY, length=0, pad=10)
    for t in chart.get_xticklabels() + chart.get_yticklabels():
        t.set_fontproperties(sans(14))
    chart.grid(axis="y", color=RULE, linewidth=1.3)
    chart.set_axisbelow(True)
    lines, dots, ends = {}, {}, {}
    for c, col in CITIES.items():
        dc = c == "Washington"
        lines[c] = chart.plot([], [], color=col, lw=4.5 if dc else 2.6, drawstyle="steps-post",
                              solid_joinstyle="miter", zorder=4 if dc else 3)[0]
        dots[c] = chart.plot([], [], "o", color=col, ms=9 if dc else 6, zorder=5)[0]
        ends[c] = chart.text(0, 0, "", color=col, va="center", fontproperties=sans_bold(19 if dc else 14), zorder=5)
    year_text = fig.text(R, chart.get_position().y1 + 0.03, "", color=INK, fontproperties=serif_bold(44),
                         va="bottom", ha="right")
    fig.text(L, 0.035, f"Grey on the maps: parkland, left out of the lines. Today's boundaries, dated by designation.\n"
             f"Sources: DC GIS; NYC Open Data (LPC); City of Philadelphia; City of Boston; Census TIGERweb; "
             f"snapshot {snapshot()}", color=GREY, fontproperties=sans(12.5), va="baseline", linespacing=1.5)
    wm = BRAND / "Capital_Commonsense_Wordmark_Transparent_4096.png"
    if wm.exists():
        img = mpimg.imread(wm)
        h = 0.026  # figure height fraction
        w = h * img.shape[1] / img.shape[0] * 1080 / 1920
        wax = fig.add_axes([R - w, 0.026, w, h])
        wax.imshow(img)
        wax.set_axis_off()

    if FRAMES.exists():
        shutil.rmtree(FRAMES)
    FRAMES.mkdir(parents=True)
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
            ends[c].set_text(f"{SHORT[c]} {ys[-1]:.1%}")
        # End labels: keep a small gap between cities' values.
        gap_y, placed = ymax * 0.075, []
        for c in sorted(lines, key=lambda c: lines[c].get_ydata()[-1]):
            y = lines[c].get_ydata()[-1]
            y = max([y] + [p + gap_y for p in placed])
            placed.append(y)
            ends[c].set_position((tx + 0.8, y))
        year_text.set_text(str(yr))
        fig.savefig(FRAMES / f"f{i:05d}.png", facecolor=PAPER)
    plt.close(fig)
    if preview is not None:
        return FRAMES

    out = CHARTS_OUT / "comps_designated_land.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(FPS), "-i", str(FRAMES / "f%05d.png"),
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "20", "-movflags", "+faststart", str(out)],
                   check=True)
    return out


if __name__ == "__main__":
    print(render())
