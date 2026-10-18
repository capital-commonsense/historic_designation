"""Nomination charts from data/joined/nominations.csv."""

import matplotlib.pyplot as plt
import pandas as pd

from historic_preservation.charts import MUTED, PALETTE, save, style
from historic_preservation.config import ANALYSIS, JOINED

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

    fig, ax = plt.subplots(figsize=(10, 5.6))
    bottom = pd.Series(0, index=table.index)
    colors = PALETTE[:TOP_N] + ["#8C8C8C", PALETTE[5], MUTED]
    for col, color in zip(order, colors):
        ax.bar(table.index, table[col], bottom=bottom, color=color, label=col, width=0.8,
               hatch="///" if col == "Unknown" else None, edgecolor="white" if col != "Unknown" else "#999999",
               linewidth=0.4)
        bottom += table[col]
    ax.axvspan(lo - 0.5, hi + 0.5, color="#F2F2F2", zorder=0)
    ax.text((lo + hi) / 2, bottom.max() * 1.02, f"FY{lo}–{hi}: HPO's annual updates name the nominator",
            ha="center", fontsize=8, color="#555555")
    style(ax)
    ax.set_title(title, loc="left", fontsize=11.5, fontweight="bold")
    ax.set_ylabel("Nominations decided by HPRB")
    ax.set_xlabel("Fiscal year of decision")
    ax.set_xticks(table.index)
    ax.set_xticklabels([str(y)[2:] if y % 2 else str(y) for y in table.index], fontsize=8)
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

    fig, ax = plt.subplots(figsize=(10, 5.2))
    ax.bar(later.index, later["landmark"], color=PALETTE[0], label="Landmarks", width=0.8)
    ax.bar(later.index, later["district"], bottom=later["landmark"], color=PALETTE[1], label="Historic districts", width=0.8)
    style(ax)
    ax.set_ylabel("Designations")
    ax.legend(frameon=False, fontsize=8.5)
    ax.text(1965, later.sum(axis=1).max() * 0.95,
            f"1964 (not shown): {first} entries on the first DC list", fontsize=8, color="#555555")
    ax.set_title(f"After the 1964 list, DC added landmarks and districts most quickly in {peak} "
                 f"({int(later.loc[peak].sum())})", loc="left", fontsize=11.5, fontweight="bold")
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

    fig, ax = plt.subplots(figsize=(10, 5.4))
    bottom = pd.Series(0, index=t.index)
    for col, color in (("designated", PALETTE[0]), ("denied", PALETTE[5]), ("withdrawn", PALETTE[1])):
        for ok in (True, False):
            sub = t["adequate_coverage"] == ok
            ax.bar(t.index[sub], t.loc[sub, col], bottom=bottom[sub], color=color if ok else MUTED,
                   label=col.capitalize() if ok else None, width=0.8, edgecolor="white", linewidth=0.4,
                   hatch=None if ok else "///")
        bottom += t[col]
    opp = t["hpo_owner_opposed_approved"].fillna(0) + t["hpo_owner_opposed_denied"].fillna(0)
    ax.scatter(t.index[opp > 0], bottom[opp > 0] + 0.6, marker="v", color="#000000", s=18,
               label="HPO reports owner opposition (count printed)")
    for fy, k in opp[opp > 0].items():
        ax.text(fy, bottom[fy] + 1.1, f"{int(k)}", ha="center", fontsize=7)
    style(ax)
    ax.set_ylabel("Nominations decided (landmarks and districts)")
    ax.set_xlabel("Fiscal year of decision; grey hatched = years whose scraped coverage of HPO's counts is below 0.8")
    ax.set_xticks(t.index)
    ax.set_xticklabels([str(y)[2:] if y % 2 else str(y) for y in t.index], fontsize=8)
    ax.legend(frameon=False, fontsize=8.5, loc="upper left", bbox_to_anchor=(1.0, 1.0))
    ax.set_title(f"In the {span}, {rate:.0%} of decided nominations were designated "
                 f"({int(good['designated'].sum())} of {int(decided)})", loc="left", fontsize=11.5, fontweight="bold")
    fig.subplots_adjust(bottom=0.2)
    save(fig, "nomination_outcomes", t,
         "Nomination outcomes by fiscal year of the HPRB decision (amendments count as designated). Withdrawals are "
         "undercounted: most nominations withdrawn before a hearing leave no public record. Owner-opposition counts "
         "are HPO's annual-report figures, not matched to individual cases. Sources: data/joined/nominations.csv, "
         "data/analysis/coverage_by_year.csv.")


FILER_TYPES = (("dcpl", "DC Preservation League", PALETTE[0]), ("neighborhood_society", "Neighborhood societies", PALETTE[2]),
               ("neighborhood_adhoc", "Ad hoc neighborhood groups", PALETTE[4]), ("anc", "ANCs", PALETTE[6]),
               ("citywide_other", "Other citywide groups", PALETTE[3]), ("government", "Government", "#8C8C8C"),
               ("owner", "Property owners (incl. co-filed)", PALETTE[5]), ("other", "Other", "#555555"),
               ("unknown", "Unknown", MUTED))


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

    fig, (ax, ax2) = plt.subplots(1, 2, figsize=(12, 5.6))
    for axis, table, ylabel in ((ax, t, "Nominations decided"), (ax2, v, "Today's assessed value of designated property")):
        bottom = pd.Series(0.0, index=table.index)
        for key, name, color in FILER_TYPES:
            axis.bar(table.index, table[key], bottom=bottom, color=color, label=name, width=0.7,
                     hatch="///" if key == "unknown" else None, edgecolor="#999999" if key == "unknown" else "white",
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
    fig.suptitle(f"In the 2010s, {label} filed {int(recent[lead])} of {int(known)} decided nominations with a known "
                 f"filer; {dict((k, n) for k, n, _ in FILER_TYPES)[vlead]} filings cover the most designated value "
                 f"({pct_share(rv[vlead], rv.sum())})", x=0.01, ha="left", fontsize=11.5, fontweight="bold")
    fig.subplots_adjust(bottom=0.2, top=0.86, wspace=0.28)
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
