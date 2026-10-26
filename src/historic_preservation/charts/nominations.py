"""Nomination charts from data/joined/nominations.csv."""

import matplotlib.pyplot as plt
from matplotlib.transforms import ScaledTranslation
import pandas as pd

from historic_preservation.charts import (BLUE, DARK, GOLD, GREEN, GREY, INK, LIGHT, MID, MOBILE_WIDTH, PAPER, RED, headline,
                                          mobile, pick, save, sparse_years, style)
from historic_preservation.config import ANALYSIS, INPUTS, JOINED

DECIDED = ("designated", "amended", "denied", "withdrawn", "de-designated")
TOP_N = 5
WELL_ATTRIBUTED = (2010, 2022)  # fiscal years whose HPO updates name nominators


def entities() -> pd.DataFrame:
    """Decided nominations FY2006+, with the first-named filer as the entity."""
    n = pd.read_csv(JOINED / "nominations.csv")
    d = n[n["outcome"].isin(DECIDED) & (n["fy"] >= 2006) & (n["kind"] != "thematic_document")].copy()
    d["fy"] = d["fy"].astype(int)
    d["entity"] = d["filers"].fillna("").str.split("; ").str[0]
    d.loc[d["filer_type"].isin(["owner", "owner_cosponsor"]), "entity"] = "Property owners"
    d.loc[d["entity"].isin(["individual", "private owner"]), "entity"] = "Individuals"
    d.loc[d["filer_type"] == "unknown", "entity"] = "Unknown"
    return d


def by_entity_and_year() -> None:
    d = entities()
    named = d[~d["entity"].isin(["Unknown", "Property owners", "Individuals"])]
    top = named["entity"].value_counts().head(TOP_N).index.tolist()
    d["group"] = d["entity"].where(d["entity"].isin(top + ["Property owners", "Unknown"]), "Other named filers")
    order = top + ["Other named filers", "Property owners", "Unknown"]
    table = d.pivot_table(index="fy", columns="group", values="nomination_id", aggfunc="count", fill_value=0)
    table = table.reindex(columns=order, fill_value=0).reindex(range(d["fy"].min(), d["fy"].max() + 1), fill_value=0)

    lo, hi = WELL_ATTRIBUTED
    window = table.loc[lo:hi]
    attributed = window.drop(columns="Unknown").to_numpy().sum()
    leader = window.drop(columns=["Unknown", "Other named filers", "Property owners"]).sum().idxmax()
    lead_n = int(window[leader].sum())
    title = (f"{leader} filed {lead_n} of {attributed} nominations with a known filer decided in FY{lo}–{str(hi)[2:]}"
             f" ({lead_n / attributed:.0%})")

    fig, ax = plt.subplots(figsize=pick((10, 5.6), (MOBILE_WIDTH, 6.6)))
    bottom = pd.Series(0, index=table.index)
    # Red: the leading filer the headline names; other named filers in ink and the shared hues.
    others = iter([INK, BLUE, GREEN, GOLD, DARK])
    colors = {**{e: RED if e == leader else next(others) for e in top},
              "Other named filers": MID, "Property owners": DARK if leader in top[:4] else GREY, "Unknown": PAPER}
    for col in order:
        # Phones: the longest name shortened, so the legend fits two columns.
        label = pick(col, col.replace("Department", "Dept."))
        ax.bar(table.index, table[col], bottom=bottom, color=colors[col], label=label, width=0.8,
               hatch="///" if col == "Unknown" else None, edgecolor=MID if col == "Unknown" else PAPER,
               linewidth=0.4)
        bottom += table[col]
    ax.axvspan(lo - 0.5, hi + 0.5, color="#F4F3F0", zorder=0)
    ax.text((lo + hi) / 2, bottom.max() * 1.02, f"FY{lo}–{hi}: HPO's annual updates name the nominator",
            ha="center", fontsize=8, color=GREY)
    style(ax)
    headline(fig, title, f"Landmark and district nominations decided by HPRB, by first-named filer, "
                         f"FY{table.index.min()}–{table.index.max()}")
    ax.set_ylabel("Nominations decided by HPRB")
    ax.set_xlabel("Fiscal year of decision")
    ax.set_xticks(table.index)
    ax.set_xticklabels(pick([str(y)[2:] if y % 2 else str(y) for y in table.index], sparse_years(table.index)), fontsize=8)
    ax.legend(loc="upper left", bbox_to_anchor=(1.0, 1.0), frameon=False, fontsize=8.5, title="First-named filer",
              title_fontsize=8.5, reverse=True)
    fig.subplots_adjust(bottom=0.16)
    save(fig, "nominations_by_entity_year", table,
         "Counts landmark and district nominations HPRB designated, amended, denied, withdrew or revoked, by fiscal "
         "year of the decision, by first-named filer; nominations an owner filed or co-filed are counted as 'Property owners'. Filers from HPO's Inventory updates (FY2010–22), "
         "HPO staff reports and HPRB actions; types inferred from names. 'Unknown': no source names the filer, "
         "mostly FY2006–09 and FY2023–26. Source: data/joined/nominations.csv.")


def inventory_additions_per_year() -> None:
    n = pd.read_csv(JOINED / "nominations.csv", parse_dates=["outcome_date"])
    d = n[n["outcome"].eq("designated") & n["kind"].isin(["landmark", "district"]) & n["outcome_date"].notna()].copy()
    d["year"] = d["outcome_date"].dt.year
    t = d.pivot_table(index="year", columns="kind", values="nomination_id", aggfunc="count", fill_value=0)
    t = t.reindex(range(1964, int(d["year"].max()) + 1), fill_value=0).reindex(columns=["landmark", "district"], fill_value=0)
    first = int(t.loc[1964].sum())
    later = t.drop(index=1964)
    peak = later.sum(axis=1).idxmax()

    fig, ax = plt.subplots(figsize=pick((10, 5.2), (MOBILE_WIDTH, 5.6)))
    ax.bar(later.index, later["landmark"], color=INK, label="Landmarks", width=0.8)
    ax.bar(later.index, later["district"], bottom=later["landmark"], color=MID, label="Historic districts", width=0.8)
    ax.text(peak, later.loc[peak].sum(), f"{int(later.loc[peak].sum())}", ha="center", va="bottom", color=INK,
            fontweight="semibold")
    style(ax)
    ax.set_ylabel("Designations")
    ax.legend(frameon=False, fontsize=8.5)
    ax.text(pick(1965, later.index.max()), later.sum(axis=1).max() * 0.95,  # phones: top right, clear of the peak
            f"1964 (not shown): {first} entries{pick(' ', chr(10))}on the first DC list", fontsize=8, color=GREY,
            ha=pick("left", "right"), va=pick("baseline", "top"))
    headline(fig, f"After the 1964 list, DC added landmarks and districts most quickly in {peak} "
             f"({int(later.loc[peak].sum())})", f"Designations per calendar year, 1965–{later.index.max()}")
    fig.subplots_adjust(bottom=0.18)
    save(fig, "inventory_additions_per_year", t,
         "Landmarks and historic districts designated per calendar year, from the 2009 DC Inventory, HPO's annual "
         "Inventory updates and HPRB actions, reconciled (data/joined/nominations.csv). Amendments and boundary "
         "expansions are not counted; dates before about 2006 come from the Inventory alone.")


def nomination_outcomes() -> None:
    n = pd.read_csv(JOINED / "nominations.csv")
    cov = pd.read_csv(ANALYSIS / "coverage_by_year.csv").set_index("fy")
    d = n[n["outcome"].isin(["designated", "amended", "denied", "withdrawn"]) & (n["fy"] >= 2002)].copy()
    d["fy"] = d["fy"].astype(int)
    d["result"] = d["outcome"].replace({"amended": "designated"})
    t = d.pivot_table(index="fy", columns="result", values="nomination_id", aggfunc="count", fill_value=0)
    t = t.reindex(range(2002, int(d["fy"].max()) + 1), fill_value=0)
    t = t.reindex(columns=["designated", "denied", "withdrawn"], fill_value=0)
    t["adequate_coverage"] = cov["adequate"].reindex(t.index).fillna(False).astype(bool)
    t["hpo_owner_opposed_approved"] = cov["hpo_approved_owner_opposed"].reindex(t.index)
    t["hpo_owner_opposed_denied"] = cov["hpo_denied_owner_opposed"].reindex(t.index)
    good = t[t["adequate_coverage"]]
    decided = good[["designated", "denied", "withdrawn"]].to_numpy().sum()
    rate = good["designated"].sum() / decided
    span = f"{len(good)} adequately covered years, FY{good.index.min()}–{str(good.index.max())[2:]}"

    fig, ax = plt.subplots(figsize=pick((10, 5.4), (MOBILE_WIDTH, 6.4)))
    bottom = pd.Series(0, index=t.index)
    for col, color in (("designated", INK), ("denied", DARK), ("withdrawn", MID)):
        for ok in (True, False):
            sub = t["adequate_coverage"] == ok
            ax.bar(t.index[sub], t.loc[sub, col], bottom=bottom[sub], color=color if ok else LIGHT,
                   label=col.capitalize() if ok else None, width=0.8, edgecolor=PAPER, linewidth=0.4,
                   hatch=None if ok else "///")
        bottom += t[col]
    # One red mark per owner-opposed case HPO reports, beside the segment of its outcome (designated or denied),
    # stacked up the segment's middle; a year with no scraped denials puts its denied marks at the segment's base.
    mark = 5 / 72  # inches between stacked marks
    for col, opp_col in (("designated", "hpo_owner_opposed_approved"), ("denied", "hpo_owner_opposed_denied")):
        low = t["designated"] * (col == "denied")
        mid = low + t[col] / 2
        for fy, k in t[opp_col].fillna(0).astype(int).items():
            for i in range(k):
                shift = ScaledTranslation(0, (i - (k - 1) / 2) * mark, fig.dpi_scale_trans)
                ax.plot(fy - 0.47, mid[fy], marker=">", color=RED, ms=4.2, ls="none", transform=ax.transData + shift,
                        clip_on=False)
    ax.plot([], [], marker=">", color=RED, ms=5, ls="none",
            label="HPO reports owner opposition")
    style(ax)
    ax.set_ylabel("Nominations decided\n(landmarks and districts)")
    ax.set_xlabel("Fiscal year of decision; grey hatched = years whose scraped coverage of HPO's counts is below 0.8")
    ax.set_xticks(t.index)
    ax.set_xticklabels(pick([str(y)[2:] if y % 2 else str(y) for y in t.index], sparse_years(t.index)), fontsize=8)
    ax.legend(frameon=False, fontsize=8.5, loc="upper right")  # over the low recent years, so the plot gets the width
    headline(fig, f"In the {span}, {rate:.0%} of decided nominations were designated "
             f"({int(good['designated'].sum())} of {int(decided)})",
             f"Landmark and district nominations by HPRB outcome, FY{t.index.min()}–{t.index.max()}")
    fig.subplots_adjust(bottom=0.2, right=0.98)
    save(fig, "nomination_outcomes", t,
         "Nomination outcomes by fiscal year of the HPRB decision (amendments count as designated). Withdrawals are "
         "undercounted: most nominations withdrawn before a hearing leave no public record. Owner-opposition counts "
         "are HPO's annual-report figures (approved or denied over the owner's objection), one mark per case beside that "
         "outcome's segment; HPO does not name the cases, so marks are not matched to individual nominations. Sources: data/joined/nominations.csv, "
         "data/analysis/coverage_by_year.csv.")


# Red goes to whichever type leads the 2010s (the headline's finding); see by_filer_type.
FILER_TYPES = (("dcpl", "DC Preservation League", INK), ("neighborhood_society", "Neighborhood societies", BLUE),
               ("neighborhood_adhoc", "Ad hoc neighborhood groups", "#8DB3CF"), ("anc", "ANCs", GOLD),
               ("citywide_other", "Other citywide groups", GREEN), ("government", "Government", DARK),
               ("owner", "Property owners (incl. co-filed)", MID), ("other", "Other", LIGHT),
               ("unknown", "Unknown", PAPER))


def by_filer_type() -> None:
    n = pd.read_csv(JOINED / "nominations.csv")
    d = n[n["outcome"].isin(DECIDED) & n["fy"].notna() & (n["fy"] >= 1980) & (n["kind"] != "thematic_document")].copy()
    d["decade"] = (d["fy"].astype(int) // 10 * 10).astype(str) + "s"
    d["type"] = d["filer_type"].replace({"owner_cosponsor": "owner"})
    t = d.pivot_table(index="decade", columns="type", values="nomination_id", aggfunc="count", fill_value=0)
    t = t.reindex(columns=[k for k, _, _ in FILER_TYPES], fill_value=0)

    # Today's assessed value of the tax records each designated nomination covers (join/nomination_lots.py).
    links = pd.read_csv(JOINED / "nomination_lots.csv")
    roll = pd.read_parquet(JOINED / "itspe_status.parquet", columns=["ssl", "assessment"]).groupby("ssl")["assessment"].sum()
    value = links.assign(v=links["ssl"].map(roll)).groupby("nomination_id")["v"].sum()
    des = d[d["outcome"] == "designated"].copy()
    des["value"] = des["nomination_id"].map(value)
    v = des.pivot_table(index="decade", columns="type", values="value", aggfunc="sum", fill_value=0)
    v = v.reindex(index=t.index, columns=[k for k, _, _ in FILER_TYPES], fill_value=0)
    linked = des["value"].notna().groupby(des["decade"]).mean()

    recent = t.loc["2010s"]
    known = recent.drop("unknown").sum()
    lead = recent.drop(["unknown"]).idxmax()
    label = dict((k, v) for k, v, _ in FILER_TYPES)[lead]
    rv = v.loc["2010s"].drop("unknown")
    vlead = rv.idxmax()

    fig, (ax, ax2) = plt.subplots(*pick((1, 2), (2, 1)), figsize=pick((12, 5.6), (MOBILE_WIDTH, 9.6)))
    for axis, table, ylabel in ((ax, t, "Nominations decided"), (ax2, v, "Today's assessed value of designated property")):
        bottom = pd.Series(0.0, index=table.index)
        for key, name, color in FILER_TYPES:
            axis.bar(table.index, table[key], bottom=bottom, color=RED if key == lead else color, label=name, width=0.7,
                     hatch="///" if key == "unknown" else None, edgecolor=MID if key == "unknown" else PAPER,
                     linewidth=0.4)
            bottom += table[key]
        style(axis)
        axis.set_ylabel(ylabel)
        axis.set_xlabel("Decade of decision (fiscal year)")
        axis.tick_params(axis="x", labelsize=8.5)
    ax2.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"${x / 1e9:,.0f}B"))
    ax.set_title("Nominations decided", loc="left", fontsize=10)
    ax2.set_title("Value designated", loc="left", fontsize=10)
    ax2.legend(loc="upper left", bbox_to_anchor=(1.0, 1.0), frameon=False, fontsize=8.5, reverse=True)
    fig.subplots_adjust(bottom=0.2, wspace=0.28, hspace=0.35)
    headline(fig, f"In the 2010s, {label} filed {int(recent[lead])} of {int(known)} decided nominations with a known "
             f"filer; {dict((k, n) for k, n, _ in FILER_TYPES)[vlead]} filings cover the most designated value "
             f"({pct_share(rv[vlead], rv.sum())})", f"Decided nominations and designated value by filer type, "
             f"{t.index[0]}–{t.index[-1]}")
    out = pd.concat({"nominations": t, "assessed_value": v}, names=["measure"])
    save(fig, "nominations_by_filer_type", out,
         "Decided landmark and district nominations by filer type (inferred from filer names; first-named filer's "
         "type, owners if an owner filed or co-filed) and decade. Filers are known mostly for FY2010–22, when HPO's "
         "Inventory updates name them; earlier decades are mostly unknown. Value: today's assessed value of the tax "
         "records each designated nomination covers, linked by district name or by landmark address and name "
         "(data/joined/nomination_lots.csv; linked share by decade: "
         + ", ".join(f"{k} {x:.0%}" for k, x in linked.items()) + "); a record inside both a district and a landmark "
         "counts in each, district values include later expansions, and some exempt parcels carry a $0 assessment. "
         "Source: data/joined/nominations.csv.")


def pct_share(a, b) -> str:
    return f"{a / b:.0%} of value with a known filer" if b else "n/a"


ATTRIBUTED_FROM = 2015  # HPO's posted staff reports name applicants, so denials can be attributed
FILER_GROUPS = (("DC Preservation League", lambda d: d["dcpl"]),
                ("Property owners", lambda d: d["filer_type"].isin(["owner", "owner_cosponsor"])),
                ("Government agencies", lambda d: d["filer_type"].eq("government")),
                ("Neighborhood groups", lambda d: d["filer_type"].isin(["neighborhood_society", "neighborhood_adhoc"])),
                ("Other preservation groups", lambda d: d["filer_type"].isin(["citywide_other", "other"])),
                ("ANCs", lambda d: d["filer_type"].eq("anc")),
                ("Filer unknown", lambda d: d["filer_type"].eq("unknown")))


def by_filer_success() -> None:
    n = pd.read_csv(JOINED / "nominations.csv")
    d = n[n["fy"].ge(ATTRIBUTED_FROM) & n["outcome"].isin(["designated", "amended", "denied", "withdrawn"])
          & (n["kind"] != "thematic_document")].copy()
    d["dcpl"] = d["filers"].fillna("").str.contains("Preservation League")
    staff = pd.read_csv(INPUTS / "hprb_staff_review.csv", dtype=str).drop_duplicates("case_no").set_index("case_no")["position"]
    d["result"] = d["outcome"].map({"designated": "designated", "amended": "designated", "withdrawn": "withdrawn",
                                    "denied": "denied"})
    d.loc[(d["result"] == "denied") & d["case_no"].map(staff).eq("grant"), "result"] = "overruled"
    d["group"] = None
    for label, test in FILER_GROUPS:  # first match wins: a DCPL co-filing counts as DCPL
        d.loc[d["group"].isna() & test(d), "group"] = label
    results = (("designated", "Designated", INK), ("overruled", "Denied though HPO recommended designation", DARK),
               ("denied", "Denied", MID), ("withdrawn", "Withdrawn", LIGHT))
    t = d.pivot_table(index="group", columns="result", values="nomination_id", aggfunc="count", fill_value=0)
    t = t.reindex(index=[g for g, _ in FILER_GROUPS], columns=[k for k, _, _ in results], fill_value=0)

    fig, ax = plt.subplots(figsize=pick((10, 4.8), (MOBILE_WIDTH, 6.4)))
    labels = list(t.index[::-1])
    left = pd.Series(0, index=labels)
    for key, name, color in results:
        vals = t.loc[labels, key]
        ax.barh(labels, vals, left=left, color=color, label=name, height=0.62)
        left += vals
    ax.barh("DC Preservation League", t.loc["DC Preservation League", "designated"], color=RED, height=0.62)
    unk = labels.index("Filer unknown")
    ax.barh(labels[unk], left.iloc[unk], color="none", edgecolor=MID, hatch="///", linewidth=0, height=0.62)
    decided = t.sum(axis=1)
    for i, g in enumerate(labels):
        ax.text(left[g] + 0.6, i, f"{t.loc[g, 'designated']} of {decided[g]} designated ({t.loc[g, 'designated'] / decided[g]:.0%})",
                va="center", fontsize=8.5)
    ax.set_xlim(0, decided.max() * 1.45)
    style(ax, grid="x")
    ax.tick_params(axis="y", labelcolor=INK)
    ax.set_xlabel("Nominations HPRB decided or that were withdrawn")
    ax.legend(loc="upper center", bbox_to_anchor=(0.4, -0.18), ncol=2, frameon=False, fontsize=8.5)
    fig.subplots_adjust(left=0.22, right=0.97, bottom=0.3)
    dc = t.loc["DC Preservation League"]
    named = t.drop(index=["DC Preservation League", "Filer unknown"]).sum()
    p_dc, p_other = dc["designated"] / dc.sum(), named["designated"] / named.sum()
    verb = "about as often as" if abs(p_dc - p_other) < 0.05 else ("less often than" if p_dc < p_other else "more often than")
    lo, hi = int(d["fy"].min()), int(d["fy"].max())
    headline(fig, f"DCPL's nominations succeed {verb} other filers': {dc['designated']} of {dc.sum()} ({p_dc:.0%}) "
             f"against {named['designated']} of {named.sum()} ({p_other:.0%})",
             f"Landmark and district nominations decided or withdrawn, by filer, FY{lo}–{hi}")
    save(fig, "nominations_success_by_filer", t,
         f"Nominations HPRB decided (designated or amended, denied) or that were withdrawn, FY{lo}–{hi}: the years "
         "when HPO's posted staff reports name the applicant, so denials as well as designations can be attributed. "
         "Filers from HPO's Inventory updates and staff reports or HPO's annual reports (inputs/filer_review.csv); "
         "a nomination DCPL filed with another group counts as DCPL's. 'Denied though HPO recommended designation' "
         "uses HPO's staff recommendation (inputs/hprb_staff_review.csv). Withdrawals before a hearing was scheduled "
         "are not in the public record. Source: data/joined/nominations.csv.")
