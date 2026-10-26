"""HPO's permit and concept reviews by type, FY2018-23: all applications, then HPRB, then the Mayor's Agent."""

import json

import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.patches import FancyArrowPatch

from historic_preservation.charts import BLUE, GOLD, GREY, INK, LIGHT, MID, MOBILE_SCALE, MOBILE_WIDTH, headline, mobile, pick, save, style
from historic_preservation.charts import RED
from historic_preservation.config import ANALYSIS

# Stacked bottom to top; red: demolition, the type that most often reaches the Mayor's Agent.
TYPES = (("demolition", "Demolition", RED), ("new_construction", "New construction", BLUE),
         ("subdivision", "Subdivision", GOLD), ("alteration_addition", "Alteration or addition", MID),
         ("other", "Other", LIGHT))
SHORT = {"demolition": "Demolition", "new_construction": "New constr.", "subdivision": "Subdivision",
         "alteration_addition": "Alteration"}
STAGES = (("all", "applications HPO handled"), ("hprb", "referred to HPRB"), ("mayors_agent", "at the Mayor's Agent"))


def review_pipeline() -> None:
    r = pd.read_csv(ANALYSIS / "hpo_review_types.csv")
    s = json.loads((ANALYSIS / "hpo_review_types_summary.json").read_text())
    data = r.pivot(index="fy", columns="type", values=[k for k, _ in STAGES])
    years = data.index
    fig = plt.figure(figsize=pick((11, 6.2), (MOBILE_WIDTH, 10.5)))
    gs = fig.add_gridspec(*pick((1, 3), (3, 1)), wspace=0.95, hspace=0.75)
    axes = [fig.add_subplot(gs[i]) for i in range(3)]
    for ax, (stage, name) in zip(axes, STAGES):
        bottom = pd.Series(0.0, index=years)
        for key, label, color in TYPES:
            v = data[(stage, key)]
            ax.bar(years, v, bottom=bottom, color=color, width=0.72, label=label)
            bottom += v
        for y, v in bottom.items():
            ax.text(y, v, f"{v:,.0f}", ha="center", va="bottom", fontsize=7.5, color=GREY)
        style(ax)
        ax.set_title(f"{s['printed_totals'][stage]:,} {name}", loc="left", fontsize=10)
        ax.set_xticks(years)
        ax.set_xticklabels([f"{y % 100:02d}" for y in years], fontsize=8)
        ax.set_ylim(0, bottom.max() * 1.12)
        ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v, _: f"{v:,.0f}"))

    t, p = s["by_type"], s["printed_totals"]
    rate = lambda a, b, k: t[k][b] / t[k][a]
    notes = (
        f"{p['hprb'] / p['all']:.1%} referred\n\n" + "\n".join(
            f"{SHORT[k]} {rate('all', 'hprb', k):.0%}" for k, _, _ in TYPES[:4]) + "\nOther 0%",
        f"{p['mayors_agent']} cases\n\n" + "\n".join(f"{SHORT[k]} {t[k]['mayors_agent']}" for k, _, _ in TYPES[:4]),
    )
    axes[pick(0, 2)].legend(loc="upper left", bbox_to_anchor=(0, -0.09), ncol=5, fontsize=8.5)

    d = t["demolition"]
    headline(fig, f"Of {p['all']:,} applications HPO handled in FY{years.min()}–{years.max()}, {p['hprb']} went to the "
                  f"review board and {p['mayors_agent']} to the Mayor's Agent; demolitions, "
                  f"{d['all'] / s['row_sums']['all']:.1%} of applications, were {d['mayors_agent']} of those {p['mayors_agent']}",
             "Permit and concept applications by type and the stage they reached, by fiscal year (each panel on its own scale)")
    if mobile():  # arrows down between the stacked panels, each with its rates on one line beside it
        lines = (f"{p['hprb'] / p['all']:.1%} referred: " + ", ".join(
                     f"{SHORT[k].lower()} {rate('all', 'hprb', k):.0%}" for k, _, _ in TYPES[:4]) + ", other 0%",
                 f"{p['mayors_agent']} cases: " + ", ".join(f"{SHORT[k].lower()} {t[k]['mayors_agent']}" for k, _, _ in TYPES[:4]))

        def arrows():
            for upper, lower, note in zip(axes, axes[1:], lines):
                a, b = upper.get_tightbbox(), lower.get_tightbbox()
                y0, y1 = fig.transFigure.inverted().transform([(0, a.y0), (0, b.y1)])[:, 1]
                x = fig.transFigure.inverted().transform((a.x0, 0))[0] + 0.02
                fig.patches.append(FancyArrowPatch((x, y0 - 0.01), (x, y1 + 0.01), transform=fig.transFigure,
                                                   arrowstyle="-|>", mutation_scale=16, color=INK, lw=1.2))
                fig.text(x + 0.04, (y0 + y1) / 2, note.replace("constr.", "construction"), ha="left", va="center",
                         fontsize=7.5 * MOBILE_SCALE, color=GREY, wrap=True)
        fig._after_layout = arrows
    fig.subplots_adjust(top=fig.subplotpars.top - 0.07, bottom=0.2)
    # after the layout is final, so the arrows sit between the panels (an override headline relays it out)
    fig.canvas.draw()
    for left, right, note in zip(axes, axes[1:], notes if not mobile() else ()):
        a, b = left.get_position(), right.get_position()
        x0, x1, y = a.x1 + 0.015, b.x0 - 0.045, a.y0 + a.height * 0.62
        fig.patches.append(FancyArrowPatch((x0, y), (x1, y), transform=fig.transFigure, arrowstyle="-|>",
                                           mutation_scale=12, color=INK, lw=1))
        fig.text((x0 + x1) / 2, y - 0.02, note, ha="center", va="top", fontsize=7.5, color=GREY, linespacing=1.3)
    off = s["rows_differ_from_printed_total"]
    save(fig, "hpo_review_pipeline", data,
         "Source: \"Permit and Concept Reviews by Type\" tables, DC HPO annual reports FY2018–2023 "
         "(inputs/hpo_review_types.csv, each row checked against the report). Stages are yearly counts, not "
         "tracked cases: a Mayor's Agent case need not have gone to HPRB that year (FY2019: 5 demolitions at the "
         "Mayor's Agent, 4 at HPRB). Rates are FY2018–23 totals. "
         + "".join(f"FY{fy}'s type rows sum to {v['all'][0]:,}, not the printed {v['all'][1]:,} (subdivisions, 277, look "
                   "out of line); the FY2023 report restates its HPRB referrals as 171, not 181. " for fy, v in off.items()
                   if "all" in v)
         + "\"Other\" through FY2022: change of use, permit revisions, temporary work, non-historic razes, interior-only "
         "work; in FY2023: code-modification, green-area-ratio and zoning-relief certifications, certificates of occupancy.")
