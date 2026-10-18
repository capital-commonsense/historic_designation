"""Mayor's Agent chart from data/normalized/mayors_agent_decisions.csv."""

import matplotlib.pyplot as plt
import pandas as pd

from historic_preservation.analysis.mayors_agent import load
from historic_preservation.charts import MUTED, PALETTE, save, style

PANELS = (("special_merit", "Special merit"), ("economic_hardship", "Economic hardship"), (None, "All decisions"))
OUTCOMES = (("granted", "Granted", PALETTE[0]), ("partial", "Partly granted", PALETTE[4]),
            ("denied", "Denied", PALETTE[5]), ("other", "Withdrawn, delayed or dismissed", MUTED))


def outcomes() -> None:
    d = load()
    d["outcome"] = d["disposition"].where(d["disposition"].isin(["granted", "partial", "denied"]), "other")
    decades = sorted(d["decade"].dropna().unique())
    fig, axes = plt.subplots(1, 3, figsize=(11, 4.6), sharey=True)
    tables = {}
    for ax, (col, label) in zip(axes, PANELS):
        sub = d if col is None else d[d[col]]
        t = sub.pivot_table(index="decade", columns="outcome", values="work_id", aggfunc="count", fill_value=0)
        t = t.reindex(index=decades, columns=[o for o, _, _ in OUTCOMES], fill_value=0)
        tables[label] = t
        bottom = pd.Series(0, index=t.index)
        for key, name, color in OUTCOMES:
            ax.bar([f"{int(x)}s" for x in t.index], t[key], bottom=bottom, color=color, label=name, width=0.7)
            bottom += t[key]
        decided = sub[sub["outcome"] != "other"]
        share = (decided["outcome"] == "granted").mean()
        ax.set_title(f"{label}: {share:.0%} granted ({(decided['outcome'] == 'granted').sum()} of {len(decided)})",
                     fontsize=9.5, loc="left")
        style(ax)
        ax.tick_params(axis="x", labelsize=8)
    axes[0].set_ylabel("Mayor's Agent decisions")
    axes[-1].legend(loc="upper left", bbox_to_anchor=(1.0, 1.0), frameon=False, fontsize=8.5, reverse=True)
    sm, eh = (d[d[c] & (d["outcome"] != "other")] for c in ("special_merit", "economic_hardship"))
    fig.suptitle(f"The Mayor's Agent granted {(sm['outcome'] == 'granted').mean():.0%} of special-merit cases "
                 f"but {(eh['outcome'] == 'granted').mean():.0%} of economic-hardship claims",
                 x=0.01, ha="left", fontsize=11.5, fontweight="bold")
    fig.subplots_adjust(top=0.82, bottom=0.2, wspace=0.08)
    data = pd.concat(tables, names=["panel"])
    save(fig, "mayors_agent_outcomes", data,
         "Mayor's Agent decisions by decade of the order, from Georgetown Law Library's collection (202 decisions, "
         "1978–2024; not a certified census). Case basis from the library's subject tags; a decision can carry both; "
         f"{int(d['subjects'].isna().sum())} decisions, including every one from the 2020s, have no tags and appear only in "
         "'All decisions'. "
         "Shares exclude withdrawn, delayed and dismissed matters. Outcomes from the library's descriptions or, where "
         "silent, the decision PDFs. Approvals with conditions count as granted. Source: "
         "data/normalized/mayors_agent_decisions.csv.")
