"""Animated comparison: designated land over time in DC, New York, Philadelphia and Boston.

Four dark maps (land, Census water, city outline) fill the frame's quadrants; each city's
designations fade in in their designation year (parkland in grey), while the line chart of
designated land share outside parkland draws on top. Frames go to tmp/frames/ (deletable) and
ffmpeg encodes charts/out/comps_designated_land.mp4. Run with `make video`.
"""

import json
import shutil
import subprocess
from pathlib import Path

import duckdb
import matplotlib

matplotlib.use("Agg")
import matplotlib.patheffects as pe  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import matplotlib.ticker as mticker  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.collections import PathCollection  # noqa: E402
from matplotlib.path import Path as MPath  # noqa: E402

from historic_preservation.charts import snapshot  # noqa: E402
from historic_preservation.config import ANALYSIS, CENSUS_PLACES, CHARTS_OUT, INPUTS, NORMALIZED, RAW  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]
FRAMES = ROOT / "tmp" / "frames"
FPS, PER_YEAR, FADE, HOLD = 30, 5, 8, 60
FIRST, LAST = 1950, pd.Timestamp.today().year
BG, LAND, EDGE, PARK = "#0b0e13", "#161b22", "#3a4250", "#5c636e"
WATER = BG  # water is cut out of the land, so nothing outside a city's outline is drawn
CITIES = {"Washington": "#E8743B", "New York": "#4AA3DF", "Philadelphia": "#3DBE8B", "Boston": "#F2C14E"}
WATER_KEYS = {"Washington": "washington", "New York": "new_york", "Philadelphia": "philadelphia", "Boston": "boston"}


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
        water = con.execute(f"""SELECT {to_merc.format(crs="'EPSG:4326'")} AS g FROM (SELECT unnest(?) AS geometry)""",
                            [[json.dumps(f["geometry"]) for f in feats if f.get("geometry")]]).df()["g"]
        out[city] = {"boundary": _path(places[CENSUS_PLACES[city]]),
                     "water": [p for p in map(_path, water) if p is not None],
                     "designations": d[d["city"] == city]}
    return out


def render(preview: list[int] | None = None) -> Path:
    """All frames and the mp4; or, with preview, only those frame numbers (no video)."""
    data = load()
    series = pd.read_csv(ANALYSIS / "comps_by_year.csv").pivot(
        index="year", columns="city", values="designated_area_share_excl_parkland")[list(CITIES)]
    ymax = float(series.max().max()) * 1.12

    fig = plt.figure(figsize=(19.2, 10.8), dpi=100, facecolor=BG)
    quads = {"Washington": (0, 0.5), "New York": (0.5, 0.5), "Philadelphia": (0, 0), "Boston": (0.5, 0)}
    groups = []  # (collection, year)
    labels = {}
    for city, (x0, y0) in quads.items():
        ax = fig.add_axes([x0 + 0.005, y0 + 0.005, 0.49, 0.49], facecolor=BG)
        ax.set_axis_off()
        b = data[city]["boundary"]
        ext = b.get_extents()
        pad = 0.03 * max(ext.width, ext.height)
        ax.add_collection(PathCollection([b], facecolor=LAND, edgecolor=EDGE, linewidth=0.8, zorder=1))
        ax.add_collection(PathCollection(data[city]["water"], facecolor=WATER, edgecolor="none", zorder=2))
        des = data[city]["designations"]
        for (year, park), g in des.groupby(["year", "parkland"]):
            paths = [p for p in map(_path, g["g"]) if p is not None]
            col = PathCollection(paths, facecolor=PARK if park else CITIES[city], edgecolor="none", alpha=0, zorder=3)
            ax.add_collection(col)
            groups.append((col, int(year)))
        ax.set_xlim(ext.x0 - pad, ext.x1 + pad)
        ax.set_ylim(ext.y0 - pad, ext.y1 + pad)
        ax.set_aspect("equal", adjustable="box", anchor="W" if x0 == 0 else "E")
        ax.text(0.03 if x0 == 0 else 0.97, 0.94 if y0 else 0.06, city.upper(), transform=ax.transAxes,
                ha="left" if x0 == 0 else "right", va="center", color=CITIES[city], fontsize=17, fontweight="bold",
                alpha=0.9)
        labels[city] = ax.text(0.03 if x0 == 0 else 0.97, 0.88 if y0 else 0.12, "", transform=ax.transAxes,
                               ha="left" if x0 == 0 else "right", va="center", color="#c9d1d9", fontsize=13)

    chart = fig.add_axes([0.14, 0.2, 0.72, 0.6])
    chart.patch.set_alpha(0)
    chart.set_xlim(FIRST, LAST)
    chart.set_ylim(0, ymax)
    chart.yaxis.set_major_locator(mticker.MultipleLocator(0.05))
    chart.yaxis.set_major_formatter(mticker.PercentFormatter(1.0, decimals=0))
    for s in chart.spines.values():
        s.set_visible(False)
    chart.tick_params(colors="#8b949e", labelsize=12, length=0)
    chart.grid(axis="y", color="#30363d", linewidth=0.8, alpha=0.7)
    chart.set_ylabel("Share of city land designated (outside parks)", color="#8b949e", fontsize=12)
    glow = [pe.Stroke(linewidth=7, foreground=BG, alpha=0.9), pe.Normal()]
    lines = {c: chart.plot([], [], color=col, lw=3, drawstyle="steps-post", path_effects=glow)[0]
             for c, col in CITIES.items()}
    ends = {c: chart.text(0, 0, "", color=col, fontsize=12, fontweight="bold", va="center", path_effects=glow)
            for c, col in CITIES.items()}
    year_text = fig.text(0.5, 0.93, "", color="#e6edf3", fontsize=56, fontweight="bold", ha="center", va="center",
                         path_effects=glow)
    fig.text(0.14, 0.835, "Share of city land inside historic districts and landmarks, excluding parkland",
             color="#e6edf3", fontsize=20, fontweight="bold", path_effects=glow)
    fig.text(0.14, 0.18, f"Today's boundaries dated by designation; parkland in grey on the maps. Sources: DC GIS, "
             f"NYC Open Data (LPC), City of Philadelphia, City of Boston, Census TIGERweb. Snapshot {snapshot()}.",
             color="#8b949e", fontsize=10, va="top", path_effects=glow)

    if FRAMES.exists():
        shutil.rmtree(FRAMES)
    FRAMES.mkdir(parents=True)
    n_frames = (LAST - FIRST + 1) * PER_YEAR + HOLD
    for i in (preview if preview is not None else range(n_frames)):
        t = min(FIRST + i / PER_YEAR, LAST + 0.999)
        for col, year in groups:
            age = (t - year) * PER_YEAR  # frames since the designation year began
            # Fade in over FADE frames, flare to full, then settle.
            col.set_alpha(0.0 if age < 0 else min(1.0, age / FADE) if age < FADE else
                          max(0.8, 1.0 - 0.2 * (age - FADE) / (2 * FADE)))
        yr = int(t)
        for c, line in lines.items():
            s = series[c].loc[:yr]
            xs = list(s.index) + [t]
            ys = list(s.values) + [s.values[-1]]
            line.set_data(xs, ys)
            ends[c].set_text(f"{ys[-1]:.0%}")
            labels[c].set_text(f"{ys[-1]:.1%} of land designated")
        # End labels: keep at least a small gap between cities' values.
        gap, placed = ymax * 0.035, []
        for c in sorted(lines, key=lambda c: lines[c].get_ydata()[-1]):
            y = lines[c].get_ydata()[-1]
            y = max([y] + [p + gap for p in placed])
            placed.append(y)
            ends[c].set_position((t + 0.6, y))
        year_text.set_text(str(yr))
        fig.savefig(FRAMES / f"f{i:05d}.png", facecolor=BG)
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
