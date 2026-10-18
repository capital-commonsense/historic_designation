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
         "1978–2024; not a certified census). Case basis from the library's subject tags, or read from the decision for "
         f"the {int(d['subjects'].isna().sum())} it left untagged (all of the 2020s); a decision can carry both. "
         "Shares exclude withdrawn, delayed and dismissed matters. Outcomes from the library's descriptions or, where "
         "silent, the decision PDFs. Approvals with conditions count as granted. Source: "
         "data/normalized/mayors_agent_decisions.csv.")


TYPES = (("demolition", "Demolition (incl. partial)"), ("subdivision", "Subdivision"),
         ("new_construction", "New construction"), ("alteration", "Alteration (windows, siding, additions…)"),
         ("procedural", "Procedural"))


def by_case_type() -> None:
    d = load()
    d["outcome"] = d["disposition"].where(d["disposition"].isin(["granted", "partial", "denied"]), "other")
    t = d.pivot_table(index="case_type", columns="outcome", values="work_id", aggfunc="count", fill_value=0)
    t = t.reindex(index=[k for k, _ in TYPES], columns=[o for o, _, _ in OUTCOMES], fill_value=0)
    fig, ax = plt.subplots(figsize=(10, 4.2))
    labels = [label for _, label in TYPES][::-1]
    left = pd.Series(0, index=t.index[::-1])
    for key, name, color in OUTCOMES:
        vals = t[key][::-1]
        ax.barh(labels, vals, left=left, color=color, label=name, height=0.6)
        left += vals
    for i, k in enumerate(t.index[::-1]):
        decided = t.loc[k, ["granted", "partial", "denied"]].sum()
        if decided:
            ax.text(left[k] + 1, i, f"{t.loc[k, 'granted'] / decided:.0%} granted", va="center", fontsize=8.5)
    style(ax)
    ax.grid(axis="x", color="#E5E5E5")
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("Mayor's Agent decisions")
    ax.legend(loc="upper center", bbox_to_anchor=(0.45, -0.2), ncol=4, frameon=False, fontsize=8.5)
    demo, alt = (t.loc[k] for k in ("demolition", "alteration"))
    share = lambda r: r["granted"] / r[["granted", "partial", "denied"]].sum()
    ax.set_title(f"The Mayor's Agent granted {share(demo):.0%} of demolition requests but {share(alt):.0%} of "
                 "alteration requests", loc="left", fontsize=11.5, fontweight="bold")
    fig.subplots_adjust(left=0.27, right=0.95, bottom=0.32)
    save(fig, "mayors_agent_by_case_type", t,
         "Mayor's Agent decisions 1978–2024 from Georgetown Law Library's collection (202; not a certified census), by "
         "the primary permit sought: demolition > subdivision > new construction > alteration, so a demolition-and-"
         "new-building project counts as demolition. Type from the library's permit type, tags and title, or read from "
         "the decision. Alteration cases are mostly owners' windows, siding, curb cuts and additions. Shares exclude withdrawn, delayed and dismissed matters. Source: "
         "data/normalized/mayors_agent_decisions.csv.")
