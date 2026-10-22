"""Mayor's Agent chart from data/normalized/mayors_agent_decisions.csv."""

import matplotlib.pyplot as plt
import pandas as pd

from historic_preservation.analysis.mayors_agent import load
from historic_preservation.charts import DARK, INK, LIGHT, MID, RED, headline, save, style

PANELS = (("special_merit", "Special merit"), ("economic_hardship", "Economic hardship"), (None, "All decisions"))
OUTCOMES = (("granted", "Granted", INK), ("partial", "Partly granted", DARK),
            ("denied", "Denied", MID), ("other", "Withdrawn, delayed or dismissed", LIGHT))


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
    fig.subplots_adjust(bottom=0.2, wspace=0.08)
    headline(fig, f"The Mayor's Agent granted {(sm['outcome'] == 'granted').mean():.0%} of special-merit cases "
             f"but {(eh['outcome'] == 'granted').mean():.0%} of economic-hardship claims",
             f"Mayor's Agent decisions by decade and basis, {int(min(decades))}s–{int(max(decades))}s")
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
    style(ax, grid="x")
    ax.tick_params(axis="y", labelcolor=INK)
    ax.set_xlabel("Mayor's Agent decisions")
    ax.legend(loc="upper center", bbox_to_anchor=(0.45, -0.2), ncol=4, frameon=False, fontsize=8.5)
    demo, alt = (t.loc[k] for k in ("demolition", "alteration"))
    share = lambda r: r["granted"] / r[["granted", "partial", "denied"]].sum()
    fig.subplots_adjust(left=0.27, right=0.95, bottom=0.32)
    headline(fig, f"The Mayor's Agent granted {share(demo):.0%} of demolition requests but {share(alt):.0%} of "
             "alteration requests", "Mayor's Agent decisions by the primary permit sought, 1978–2024")
    save(fig, "mayors_agent_by_case_type", t,
         "Mayor's Agent decisions 1978–2024 from Georgetown Law Library's collection (202; not a certified census), by "
         "the primary permit sought: demolition > subdivision > new construction > alteration, so a demolition-and-"
         "new-building project counts as demolition. Type from the library's permit type, tags and title, or read from "
         "the decision. Alteration cases are mostly owners' windows, siding, curb cuts and additions. Shares exclude withdrawn, delayed and dismissed matters. Source: "
         "data/normalized/mayors_agent_decisions.csv.")


APPLICANTS = (("government", "Public agencies"), ("business", "Developers and businesses"),
              ("institution", "Churches, nonprofits, schools"), ("individual", "Homeowners"))


def by_applicant() -> None:
    d = load()
    d["outcome"] = d["disposition"].where(d["disposition"].isin(["granted", "partial", "denied"]), "other")
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.4))
    labels = [label for _, label in APPLICANTS][::-1]
    tables = {}
    for ax, (col, title) in zip(axes, PANELS[:2]):
        t = d[d[col]].pivot_table(index="applicant_type", columns="outcome", values="work_id", aggfunc="count",
                                  fill_value=0)
        t = t.reindex(index=[k for k, _ in APPLICANTS], columns=[o for o, _, _ in OUTCOMES], fill_value=0)
        tables[title] = t
        left = pd.Series(0, index=t.index[::-1])
        for key, name, color in OUTCOMES:
            vals = t[key][::-1]
            ax.barh(labels, vals, left=left, color=color, label=name, height=0.6)
            left += vals
        for i, k in enumerate(t.index[::-1]):
            decided = t.loc[k, ["granted", "partial", "denied"]].sum()
            if decided:
                ax.text(left[k] + 0.5, i, f"{t.loc[k, 'granted']} of {decided} granted", va="center", fontsize=8.5)
        ax.set_title(f"Claimed {title.lower()} ({int(t.values.sum())} decisions)", loc="left")
        style(ax, grid="x")
        ax.tick_params(axis="y", labelcolor=INK)
    gov = tables["Special merit"].loc["government"]
    axes[0].barh(labels[-1], gov["granted"], color=RED, height=0.6)  # the finding: the city's own projects
    axes[1].tick_params(axis="y", labelleft=False)
    for ax in axes:  # room for the "x of y granted" labels
        ax.set_xlim(0, max(t.sum(axis=1).max() for t in tables.values()) * 1.4)
    axes[0].set_xlabel("Mayor's Agent decisions")
    axes[1].set_xlabel("Mayor's Agent decisions")
    axes[0].legend(loc="upper center", bbox_to_anchor=(1.0, -0.2), ncol=4, frameon=False, fontsize=8.5)
    fig.subplots_adjust(left=0.2, right=0.97, bottom=0.3, wspace=0.12)
    sm = tables["Special merit"]
    years = d.loc[d["special_merit"] | d["economic_hardship"], "order_date"].dt.year
    share = lambda k: f"{sm.loc[k, 'granted']} of {sm.loc[k, ['granted', 'partial', 'denied']].sum()}"
    headline(fig, f"Special merit worked for public agencies ({share('government')} granted) and developers "
             f"({share('business')}), not for homeowners ({share('individual')})",
             "Mayor's Agent decisions by the applicant and the ground claimed, "
             f"{years.min()}–{years.max()}")
    data = pd.concat(tables, names=["basis"])
    save(fig, "mayors_agent_by_applicant", data,
         "Mayor's Agent decisions that claimed special merit or economic hardship, from Georgetown Law Library's "
         "collection (not a certified census); a decision can claim both. Applicant read from each decision: "
         "public agencies = DC agencies (schools, fire, public works, housing and economic development), WMATA, DC Water; "
         "a joint application counts as public if an agency joined, else as business if a company joined. "
         "Institutions include one foreign government; homeowners include condominium and cooperative associations "
         "and a small landlord. Approvals with conditions count as granted. Source: "
         "data/normalized/mayors_agent_decisions.csv, inputs/mayors_agent_applicant_review.csv.")
