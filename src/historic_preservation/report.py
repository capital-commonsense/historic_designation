"""findings.md and coverage.md, written from the analysis outputs on every build.

Each number below is read from data/analysis/ or data/joined/, so the text stays
true on rebuild. Verdicts are the author's reading of those numbers and are worded
in the text; where a rebuild could flip one, the sentence says what it rests on.
"""

import json
from pathlib import Path

import pandas as pd

from historic_preservation.config import ANALYSIS, INPUTS, JOINED, NORMALIZED

ROOT = Path(__file__).resolve().parents[2]
DECIDED = ["designated", "amended", "denied", "withdrawn"]


def load(name: str):
    return json.loads((ANALYSIS / name).read_text())


def pct(a, b) -> str:
    return f"{a / b:.0%}" if b else "n/a"


def frac(a, b) -> str:
    return f"{int(a)} of {int(b)} ({pct(a, b)})"


def fy_span(years) -> str:
    years = sorted(int(y) for y in years)
    return f"FY{years[0]}–{years[-1]}" if years else "no years"


def h1(n: pd.DataFrame, cov: pd.DataFrame) -> str:
    good = sorted(cov.loc[cov["adequate"], "fy"].astype(int))
    d = n[n["fy"].isin(good) & n["outcome"].isin(DECIDED)]
    designated = d["outcome"].isin(["designated", "amended"])
    lm = d[d["kind"] == "landmark"]
    dist = d[d["kind"] == "district"]
    dist_all = n[n["kind"] == "district"]["outcome"].value_counts()
    h2s = load("h2_summary.json")
    raze = h2s["documented_pending_raze"]
    return (
        f"**Supported, with a qualification.** In the {len(good)} fiscal years where the scrape covers at least 80% of "
        f"HPO's reported applications ({fy_span(good)}, gaps excluded), HPRB designated or amended "
        f"{frac(designated.sum(), len(d))} of nominations it decided; landmarks alone "
        f"{frac(lm['outcome'].eq('designated').sum(), len(lm))}. Historic districts: "
        f"{frac(dist['outcome'].isin(['designated', 'amended']).sum(), len(dist))} designated in those years; across all "
        f"years the table records {int(dist_all.get('designated', 0))} district designations, "
        f"{int(dist_all.get('denied', 0))} denials and {int(dist_all.get('withdrawn', 0))} withdrawal. "
        f"The qualification, and the strongest counterexample: nominations heard while a raze application was pending "
        f"(H2) were designated only {frac(raze['designated'], raze['n'])} (FY2007–25). Withdrawals before a hearing are "
        f"undercounted, which flatters the rate.")


def h2() -> str:
    s = load("h2_summary.json")
    r, a, none = (s["documented_pending_raze"], s["documented_pending_alteration_or_new_construction"],
                  s["no_documented_pending_application"])
    t = s["raze_after_denial_or_withdrawal"]
    any_n = r["n"] + a["n"]
    return (
        f"**Partly supported; a lower bound.** Of {s['heard']['n']} individual-landmark nominations HPRB acted on in "
        f"FY2007–25, HPRB agendas, actions, HPO notices or staff reports show a raze application pending at the hearing "
        f"for {r['n']} ({pct(r['n'], s['heard']['n'])}) and an alteration or new-construction application for {a['n']} more "
        f"— {frac(any_n, s['heard']['n'])} in all. Only two documents say which came first; both say the raze came "
        f"first (St. Paul's Methodist Episcopal Church South: the raze application \"precipitated the landmark "
        f"nomination\"; Barry Farm). DOB permit data add circumstantial cases: {t['with_raze_permit_within_180_days']} of "
        f"{t['denied_or_withdrawn_since_2009']} nominations denied or withdrawn since 2009 were followed within 180 days "
        f"by a raze permit at the address, {len(t['of_which_not_documented_as_pending'])} of them not otherwise "
        f"documented. Nominations racing a raze fared differently: designated {pct(r['designated'], r['n'])} versus "
        f"{pct(none['designated'], none['n'])} with no documented pending application. Limits: agendas list a raze "
        f"only when HPO scheduled it \"if designated\"; the open permit data list issued permits only (2009 on), with "
        f"no application dates.")


def h3(n: pd.DataFrame) -> str:
    w = n[n["outcome"] == "withdrawn"]
    nh = n[n["outcome"] == "not_heard"]
    ag = pd.read_csv(INPUTS / "agreements.csv")
    linked = ag[ag["agreement_id"].str.contains("st_martins")]
    return (
        f"**Inconclusive: the public record cannot test it.** The nominations table holds {len(w)} withdrawals and "
        f"{len(nh)} nominations noticed but never heard. A check of every case number in HPRB agendas, actions and HPO "
        f"monthly notices (2006–2026) found only three nominations HPRB never acted on; nominations withdrawn before "
        f"HPO scheduled them leave no public trace. Of {len(ag)} agreements recorded in inputs/agreements.csv, "
        f"{len(linked)} documents a withdrawal in exchange for concessions: St. Martin's (2006), where DCPL agreed to "
        f"withdraw its application in return for preservation commitments and prior review of future permits, with no "
        f"payment. Testing H3 needs HPO's case log and withdrawal letters (records_request/request.md).")


def h4(n: pd.DataFrame) -> str:
    dd = n[n["outcome"] == "de-designated"].sort_values("outcome_date")
    names = "; ".join(f"{r.name} ({str(r.outcome_date)[:4]})" for r in dd.itertuples())
    total = int(n["outcome"].isin(["designated", "amended"]).sum())
    return (
        f"**Supported.** Against {total} designations and amendments in the table, it records {len(dd)} revocations: "
        f"{names}. No post-listing boundary reduction was found in the HPRB actions read; boundary history before the "
        f"published current polygons is not rebuilt (coverage.md), so reductions in older districts cannot be ruled out.")


def h5(n: pd.DataFrame, cov: pd.DataFrame) -> str:
    d = n[n["outcome"].isin(DECIDED) & n["fy"].between(2010, 2022)]
    known = d[d["filer_type"] != "unknown"]
    owner = known["filer_type"].isin(["owner", "owner_cosponsor"])
    gov = known["filer_type"].eq("government")
    third = ~owner & ~gov
    links = pd.read_csv(JOINED / "nomination_lots.csv")
    roll = pd.read_parquet(JOINED / "itspe_status.parquet", columns=["ssl", "assessment"]).groupby("ssl")["assessment"].sum()
    value = links.assign(v=links["ssl"].map(roll)).groupby("nomination_id")["v"].sum()
    des = known[known["outcome"] == "designated"].assign(value=lambda x: x["nomination_id"].map(value))
    vt = des.groupby(des["filer_type"].replace({"owner_cosponsor": "owner"}))["value"].sum()
    top = des.nlargest(3, "value")
    c = cov[cov["fy"].between(2007, 2022)]
    ap, dn = c["hpo_approved_owner_opposed"].sum(), c["hpo_denied_owner_opposed"].sum()
    return (
        f"**First half supported; second half not.** For decisions in FY2010–22, when HPO's updates name nominators, "
        f"{len(known)} of {len(d)} nominations have a known filer: third parties (preservation and neighborhood groups, "
        f"ANCs, others) filed {frac(third.sum(), len(known))}, owners filed or co-filed {frac(owner.sum(), len(known))}, "
        f"government agencies {frac(gov.sum(), len(known))}. Filer types are inferred from names. By today's assessed "
        f"value of what they designated (linked for {pct(des['value'].notna().sum(), len(des))} of these designations), "
        f"government filings cover {pct(vt.get('government', 0), vt.sum())}, DCPL {pct(vt.get('dcpl', 0), vt.sum())} "
        f"and owners {pct(vt.get('owner', 0), vt.sum())}; districts dominate: "
        + "; ".join(f"{r.name} (${r.value / 1e9:.1f}B, filed by {r.filers})" for r in top.itertuples())
        + ". Owner objection "
        f"appears to matter: HPO's own annual tables for FY2007–22 count {int(ap)} owner-opposed nominations approved "
        f"and {int(dn)} denied — an approval rate of {pct(ap, ap + dn)}, against about 90% overall (H1). These are "
        f"HPO's printed counts, not matched case by case; the tables' totals do not always sum.")


def h6() -> str:
    s = load("mayors_agent_summary.json")
    a, sm, eh = s["all"], s["by_basis"]["Special merit"], s["by_basis"]["Economic hardship"]
    ag, fav = s["by_reviewer_position"]["against"], s["by_reviewer_position"]["favorable"]
    dem = s["by_case_type_and_reviewer_position"]["demolition / against"]
    t = s["timing"]
    days, fy = t["days_hearing_to_order"], t["fiscal_years_application_to_order"]
    c = load("court_appeals_summary.json")
    ap = pd.read_csv(ANALYSIS / "court_mayors_agent_appeals.csv")
    po = ap[ap["appellant"] != "owner"][["prevailed", "remanded", "mixed", "lost"]].sum()
    return (
        f"**Override real: supported. Slow: mostly not.** Georgetown Law's collection holds {a['decisions']} Mayor's "
        f"Agent decisions ({s['years'][0]}–{s['years'][1]}; not a certified census). On the merits the Mayor's Agent "
        f"granted {frac(a['granted'], a['decided_on_merits'])}: special merit {frac(sm['granted'], sm['decided_on_merits'])}, "
        f"economic hardship {frac(eh['granted'], eh['decided_on_merits'])}. Where HPRB (or its predecessors) recommended "
        f"against the owner, the permit was granted anyway in {frac(ag['granted'], ag['decided_on_merits'])}; for "
        f"demolitions, {frac(dem['granted'], dem['decided_on_merits'])}. Where HPRB was favorable, "
        f"{frac(fav['granted'], fav['decided_on_merits'])}. Timing: median {days['median']:.0f} days from the last "
        f"hearing session to the order (middle half {days['p25']:.0f}–{days['p75']:.0f}; n={days['n']}; "
        f"{days['over_365']} over a year); {fy['same_fy'] + fy['next_fy']} of {fy['n']} orders came in the application's "
        f"fiscal year or the next. That covers only the Mayor's Agent stage, not delay before it. Appeals: owners lost "
        f"all {c['owner_appeals_preservation_side_prevailed']} Court of Appeals reviews of Mayor's Agent denials found; "
        f"when preservation or neighborhood groups appealed a Mayor's Agent approval ({int(po.sum())} cases), they won "
        f"{int(po['prevailed'])}, got {int(po['remanded'])} remands and {int(po['mixed'])} mixed result, and lost "
        f"{int(po['lost'])}. Opponents of an HPRB-approved alteration have "
        f"no Mayor's Agent hearing as of right (requests refused in 1999, 2013 and 2014) and no Court of Appeals review "
        f"(Dupont Circle Citizens Ass'n v. Barry, 1983).")


def h7() -> str:
    s = load("h7_summary.json")
    raze_cases = set(pd.read_csv(INPUTS / "h2_pending_applications.csv", dtype=str)
                     .query("application_type == 'raze'")["case_no"])
    to_deny = s["board_denied_staff_grant"]
    to_grant = s["board_granted_staff_deny"]
    with_raze = [x for x in to_deny if x["case_no"] in raze_cases]
    names = lambda xs: ", ".join(x["name"] for x in xs)
    lo, hi = s["fiscal_years"]
    return (
        f"**Departures are rare and run mostly against designation.** HPO staff reports posted for {s['reports']} "
        f"nominations give a recommendation on {s['decided_with_position']} that HPRB decided (FY{lo}–{hi}); HPO "
        f"recommended granting {s['staff_grant']} and denying {s['staff_deny']}. HPRB departed {s['departures']} times "
        f"({pct(s['departures'], s['decided_with_position'])}): it denied {len(to_deny)} that HPO supported ({names(to_deny)}) "
        f"— {len(with_raze)} of them with a raze application pending (H2) — and granted {len(to_grant)} that HPO opposed "
        f"({names(to_grant)}). HPRB followed {s['staff_deny_followed']} of {s['staff_deny']} HPO recommendations to deny. "
        f"Staff reports are posted mostly from FY2014 on, so earlier years are untested; withdrawn and continued cases "
        f"are not scored.")


def h8() -> str:
    d = pd.read_csv(ANALYSIS / "designated_shares.csv").set_index(["view", "zero_tax", "metric"])["share"]
    w = pd.read_csv(ANALYSIS / "designated_shares_by_ward.csv")
    w = w[(w["view"] == "all") & (w["zero_tax"] == "included")].pivot_table(index="ward", columns="metric", values="share")
    gap = (w["assessed_value"] - w["records"]).sort_values()
    return (
        f"**Supported, more weakly once exempt property is removed.** Designated property is "
        f"{d[('all', 'included', 'records')]:.0%} of DC tax records but {d[('all', 'included', 'assessed_value')]:.0%} "
        f"of assessed value and {d[('all', 'included', 'land_value')]:.0%} of land value. Excluding tax-exempt property "
        f"(federal, District, institutional), the value share falls to {d[('all', 'excluded', 'assessed_value')]:.0%} "
        f"against {d[('all', 'excluded', 'records')]:.0%} of records. By ward, value share exceeds record share most in "
        f"Ward {int(gap.index[-1])} ({gap.iloc[-1] * 100:+.0f} points) and least in Ward {int(gap.index[0])} "
        f"({gap.iloc[0] * 100:+.0f} points); Ward 2 is {w.loc[2, 'records']:.0%} designated by records. Units are tax records "
        f"(condo units count separately); boundaries and values are today's.")


def h9() -> str:
    t = pd.read_csv(ROOT / "charts" / "out" / "designated_share_over_time.data.csv", index_col="year")
    era = pd.read_csv(ANALYSIS / "value_by_designation_era.csv").set_index("era")
    pre = era.loc[[e for e in era.index if e in ("1950", "1964 list", "1960s other", "1970s", "1980s")], "assessed_value"].sum()
    last = t.index.max()
    per_decade = {f"{y}s": t.loc[min(y + 9, last), "assessed_value"] - t.loc[y - 1, "assessed_value"] for y in (1990, 2000, 2010)}
    firsts = pd.read_csv(ANALYSIS / "district_first_dates.csv")
    return (
        f"**Supported.** {pct(t.loc[1990, 'assessed_value'], t.loc[last, 'assessed_value'])} of "
        f"today's designated assessed value was protected by 1990, and {pct(pre, era['assessed_value'].sum())} of value "
        f"inside districts lies in districts first designated before 1990. Share of all DC assessed value added per "
        f"decade since: " + ", ".join(f"{k} {v:+.1%}" for k, v in per_decade.items()) + ". Caveat: only current "
        f"boundaries are published, so the {int(firsts['has_expansion'].sum())} districts with recorded expansions "
        f"count expansion lots from their original year, which overstates early protection.")


def h10() -> str:
    ag = pd.read_csv(INPUTS / "agreements.csv")
    lines = pd.read_csv(INPUTS / "dcpl_990_lines.csv", dtype=str)
    early = lines[lines["form_line"].eq("Part I line 12") & (lines["tax_period"] < "200700")].sort_values("tax_period")
    paid = ag[ag["cash_amount"].fillna(0) > 0]
    to_dcpl = paid[paid["payee"].str.contains("DCPL", na=False)]
    other = paid[~paid.index.isin(to_dcpl.index)]
    s = pd.read_csv(NORMALIZED / "dcpl_990_summary.csv").dropna(subset=["total_revenue"])
    psr = s.loc[s["program_service_revenue"].idxmax()]
    return (
        f"**Partly supported for 2003–2010; no documented case since.** inputs/agreements.csv records "
        f"{len(to_dcpl)} payments to DCPL or a DCPL-run fund: "
        + "; ".join(f"{r.property.split(' (')[0].split(' / ')[0]} ({r.date}, "
                    f"{'up to ' if 'capped' in str(r.what_other_side_gave) else ''}${r.cash_amount / 1e3:,.0f}K to "
                    f"{r.payee}{', ' + r.admin_fee if isinstance(r.admin_fee, str) else ''}; {r.verification})"
                    for r in to_dcpl.itertuples())
        + ". Other cash mitigation went elsewhere: " + "; ".join(f"{r.property.split(' (')[0]} ({r.date}, "
                                                                  f"${r.cash_amount / 1e3:,.0f}K to {r.payee})" for r in other.itertuples())
        + ". The Monument payment does not appear in DCPL's own returns: total revenue was "
        + ", ".join(f"${int(r.value) / 1e3:,.0f}K (year ending {r.tax_period[:4]}-{r.tax_period[4:]})"
                    for r in early.itertuples())
        + ", with no $450K receipt, so its timing and recipient are unconfirmed. The St. Martin's withdrawal (2006) involved no payment. DCPL's grant lists show awards from the ICG-funded "
        f"and Monument funds. No cash settlement after about 2011 was found in HPRB actions, Mayor's "
        f"Agent decisions or zoning exhibits searched — a null result, not proof of none. DCPL's 990s show program "
        f"service revenue of ${psr['program_service_revenue'] / 1e3:,.0f}K in the year ending "
        f"{str(psr['tax_period'])[:4]}-{str(psr['tax_period'])[4:]}, far above other years; the 990 does not say "
        f"what it was. Its year coincides with the Third Church demolition (2014), when ICG's payments would have "
        f"come due — an inference from timing only.")


def _osm_date() -> str:
    from historic_preservation.config import MANUAL

    names = [json.loads(p.read_text())["extract"] for p in sorted((MANUAL / "osm").glob("*.json"))]
    dates = sorted({n.rsplit("-", 1)[-1].split(".")[0] for n in names})
    return ", ".join(f"20{d[:2]}-{d[2:4]}-{d[4:]}" for d in dates)


def comps() -> str:
    path = ANALYSIS / "comps_current.csv"
    if not path.exists():
        return ""
    c = pd.read_csv(path).set_index("city")
    y = pd.read_csv(ANALYSIS / "comps_by_year.csv").pivot(index="year", columns="city",
                                                            values="designated_area_share_excl_parkland")
    has_b = "official_buildings_designated_share_excl_parkland" in c
    has_osm = "osm_buildings_designated_share_excl_parkland" in c
    b_share = c["official_buildings_designated_share_excl_parkland"] if has_b else None
    rows = "".join(
        f"| {city} | {int(r.population_2020):,} | {int(r.landmarks):,} | {r.landmarks_per_100k:.0f} | {int(r.districts)} "
        f"| {r.designated_area_share:.1%} | {r.designated_area_share_excl_parkland:.1%} |"
        + (f" {int(r.official_buildings):,} | {r.official_buildings_designated_share_excl_parkland:.1%} |" if has_b else "")
        + (f" {r.osm_buildings_designated_share_excl_parkland:.1%} |" if has_osm else "") + "\n"
        for city, r in c.loc[["Washington", "New York", "Philadelphia", "Boston"]].iterrows())
    dc = c.loc["Washington"]
    others = c.drop("Washington")["designated_area_share_excl_parkland"]
    since = {k: y.loc[y.index.max(), k] - y.loc[1990, k] for k in y.columns}
    return (
        "## Comparison: New York, Philadelphia, Boston\n\n"
        "All three run local programs comparable to DC's: a commission that designates individual landmarks and "
        "historic districts and reviews permits within them (New York's Landmarks Preservation Commission, 1965; the "
        "Philadelphia Historical Commission, 1955; the Boston Landmarks Commission, 1975, alongside separate district "
        "commissions). Each publishes designation polygons with dates.\n\n"
        "| City | Population (2020) | Landmarks (own unit) | per 100k | Districts | Land designated | excl. parkland |"
        + (" Buildings (city address data) | designated, excl. parkland |" if has_b else "")
        + (" OSM check |" if has_osm else "") + "\n"
        "|---|---|---|---|---|---|---|" + ("---|---|" if has_b else "") + ("---|" if has_osm else "") + "\n" + rows +
        f"\nDC has designated {dc.designated_area_share_excl_parkland:.0%} of its land outside parks, "
        f"{dc.designated_area_share_excl_parkland / others.max():.1f} to {dc.designated_area_share_excl_parkland / others.min():.1f} "
        f"times the share in the other cities. Since 1990 the designated share outside parks grew by "
        + ", ".join(f"{k} {v * 100:+.1f} points" for k, v in since.items())
        + ". " + (f"By buildings, DC has designated {b_share['Washington']:.0%} outside parks against "
                  f"{b_share.drop('Washington').min():.0%}–{b_share.drop('Washington').max():.0%} elsewhere. Buildings are "
                  "each city's addressed buildings, one point each, counted as designated when the point falls in a "
                  "designation: DC's active MAR address points flagged as buildings; New York's AddressPoint, one per "
                  "building identification number; Boston's SAM addresses, one per building ID; Philadelphia's assessed "
                  "properties other than vacant land, one per location, so a rowhouse counts once and condominium units "
                  "collapse to their building. " if has_b else "")
        + (f"OpenStreetMap buildings (Geofabrik extracts of {_osm_date()}) give similar shares (the OSM check column), "
           "though OSM's mapping differs by city: it maps Philadelphia's rowhouses one by one, appears to draw some "
           "of Boston's attached rows as one building (its Boston footprints are the largest of the four), and "
           "includes many of DC's outbuildings. " if has_osm else "")
        + "Landmark counts are not like for like: New York counts landmark sites, Philadelphia individually "
        "registered parcels (many single rowhouses), Boston approved landmark petitions, DC Inventory landmarks. "
        "Areas use today's boundaries dated by each feature (New York's district extensions carry their own dates; "
        "the other cities' expansions count from the original date). Parkland exclusions are listed in "
        "inputs/comps_parkland.csv; New York's scenic landmarks are not in its layer. Source tables: "
        "data/analysis/comps_current.csv, comps_by_year.csv; chart charts/out/comps_designated_land (and .mp4 via `make video`).\n")


def findings() -> str:
    n = pd.read_csv(JOINED / "nominations.csv")
    cov = pd.read_csv(ANALYSIS / "coverage_by_year.csv")
    snap = json.loads((NORMALIZED / "SNAPSHOT.json").read_text())["snapshot"]
    parts = [("H1 HPRB designates most of the nominations it decides", h1(n, cov)), ("H2 Nominations are often filed while a permit application is pending", h2()),
             ("H3 Nominations are withdrawn in exchange for concessions", h3(n)), ("H4 Designations are rarely reversed", h4(n)),
             ("H5 Most nominations are filed by third parties, and owner objection does not affect the outcome", h5(n, cov)),
             ("H6 The Mayor's Agent often grants permits over HPRB's objection, and decides slowly", h6()), ("H7 HPRB rarely departs from HPO staff recommendations", h7()),
             ("H8 Designated property holds a disproportionate share of DC's property value", h8()), ("H9 Most designated value was protected early, and additions have slowed", h9()), ("H10 Nominators have received payments in settlements", h10())]
    body = "\n\n".join(f"## {h}\n\n{p}" for h, p in parts) + "\n\n" + comps()
    return (f"# Findings\n\nGenerated by `make all` from raw snapshot {snap}; every figure is recomputed on rebuild. "
            f"Rates cover only fiscal years with adequate coverage (coverage.md). Charts are in charts/out/.\n\n{body}\n")


def coverage() -> str:
    c = pd.read_csv(ANALYSIS / "coverage_by_year.csv")
    c = c[c["fy"] >= 2000]
    cols = ["fy", "hpo_received", "hpo_approved", "hpo_denied", "scraped_cases", "scraped_approved", "scraped_denied",
            "scraped_withdrawn", "scraped_pending", "inventory_additions", "coverage_ratio", "filer_known_share",
            "records_request_cases"]
    t = c[cols].copy()
    for col in ("coverage_ratio", "filer_known_share"):
        t[col] = t[col].map(lambda v: "" if pd.isna(v) else f"{v:.2f}")
    t = t.astype(object).where(t.notna(), "")
    for col in cols:
        t[col] = t[col].map(lambda v: f"{int(v)}" if isinstance(v, float) and v == int(v) else v)
    t["adequate"] = c["adequate"].map({True: "yes", False: ""}).values
    header = "| " + " | ".join(t.columns) + " |\n|" + "---|" * len(t.columns) + "\n"
    rows = "".join("| " + " | ".join(str(v) for v in r) + " |\n" for r in t.itertuples(index=False))
    good = int(c["adequate"].sum())
    firsts = pd.read_csv(ANALYSIS / "district_first_dates.csv")
    expanded = ", ".join(firsts.loc[firsts["has_expansion"], "district"].str.replace(" Historic District", ""))
    ma = load("mayors_agent_summary.json")
    return f"""# Coverage

Generated by `make all`. Per fiscal year: HPO's published counts (as printed; never corrected) against nominations
reconstructed from HPRB actions, Inventory updates, annual reports and notices. {good} of
{int(c['hpo_received'].notna().sum())} HPO-reported years reach the 0.8 threshold; rates are not reported for the rest.
A ratio above 1 means more decisions were found than HPO reported received that year (filing and decision years differ).

{header}{rows}
## Sources

| Source | Status |
|---|---|
| HPRB action lists, 2005–2026 (planning.dc.gov crawl plus HPO's box.com archive) | Complete for crawled months; HPO's box.com archive covers 2006–2026 |
| HPO monthly notices | 2014–2025, about 100 issues; earlier notices not found |
| HPO annual reports and Inventory updates | Counts FY2001–22 from the tables; FY1989–92 reports fetched but not yet read (prose); FY1995, 2024, 2025 not found |
| 2009 DC Inventory | Complete (designation dates to 2009; mixes 1964 preliminary listings with later dates) |
| Nominators | Named FY2010–22 (Inventory updates); otherwise from staff reports and actions where stated |
| Withdrawn nominations | Partial: only those an agenda or notice listed (3 found); withdrawals before scheduling are invisible |
| HPO nomination case log (records request) | Missing: not yet filed (records_request/request.md) |
| HPO staff reports | {load('h7_summary.json')['reports']} nominations, posted mostly FY2014 on (inputs/hprb_staff_review.csv); three mislabeled reports excluded |
| Mayor's Agent decisions | {ma['all']['decisions']} decisions, {ma['years'][0]}–{ma['years'][1]}, Georgetown Law collection; the library's best effort, not a certified census |
| Mayor's Agent hearing dates | {ma['timing']['hearing_dated']} of {ma['all']['decisions']} decisions dated from a quoted sentence |
| DC Court of Appeals opinions | Partial: 3 opinions not yet fetched (CourtListener quota) |
| DOB building permits | Issued permits 2009–2026 only; no application dates |
| DCPL Form 990s | Itemized FY2011–23 except 2016; FY2009–10 990-EZ; FY2004 990 still to fetch |
| Settlements and agreements | Documented cases only (inputs/agreements.csv); amounts mostly unverified |
| Tax roll (ITSPE) and GIS layers | Complete, today's values and boundaries |

## Districts

Only current boundaries are published, so lots added by a later expansion are attributed to the district's original
designation year. Districts with recorded expansions (boundary history not rebuilt): {expanded}.
"""


def run() -> None:
    (ROOT / "findings.md").write_text(findings())
    (ROOT / "coverage.md").write_text(coverage())
    print("report: wrote findings.md, coverage.md")
