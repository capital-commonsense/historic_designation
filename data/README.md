# Data dictionary

All tables are rebuilt by `make build` from the newest complete snapshot in
`data/raw/<YYYY-MM-DD>/` (or `$HP_SNAPSHOT`). Raw snapshots and `normalized/`,
`joined/` are gitignored; `analysis/` is committed.

## Raw snapshot (`data/raw/<date>/`)

| Path | Source |
|---|---|
| `arcgis/<layer>/page_*.json`, `COMPLETE.json` | DC GIS ArcGIS REST layers (see `config.ARCGIS_LAYERS`); owner names are kept only here |
| `documents/<key>.pdf`, `<key>.pdf.json` | Source PDFs with URL and SHA-256 (see `config.DOCUMENTS`) |

## Normalized (`data/normalized/`)

| File | One row per | Notes |
|---|---|---|
| `zoning_lookup.parquet` | lot (Zoning Lookup layer) | `historic_districts` is `;`-joined for overlaps |
| `itspe.parquet` | tax-roll record | owner names dropped; `is_condo` (PROPTYPE contains "Condo") and `zero_tax` (ANNUALTAX = 0) are **inferred** flags |
| `condo_relate.parquet` | condo unit | unit SSL → underlying lot SSL (`MAT_SSL`) |
| `historic_districts.csv`, `landmark_*.csv`, `potential_landmarks.csv`, `preservation_easements.csv`, `condo_one_to_many.csv` | GIS feature | attributes only |
| `inventory_2009_entries.csv` | 2009 Inventory designation entry | date clauses extracted verbatim; no interpretation |
| `inventory_update_items.csv` | item in an annual update / HPO report | name, address, `nominated_by`, `designated`, `effective`; FY2010 (scanned) not yet parsed |
| `court_opinions.csv` | DC Court of Appeals opinion cluster (CourtListener search) | term counts; `relevant` = Mayor's Agent + HPRB + Act mentions >= 3; `coded` = in `inputs/court_cases.csv` (relevant but uncoded = zoning/BZA/FOIA cases with incidental mentions); `text_fetched` false where the daily API quota stopped the download |
| `court_cases.csv` | hand-coded preservation case (two rows for a consolidated opinion) | from `inputs/court_cases.csv`; `holding_quote` is checked verbatim against the opinion text at build time; `days_order_to_opinion` only where the opinion states the agency order date |

## Joined (`data/joined/itspe_status.parquet`)

Every ITSPE record with lot-level historic status. `match_method`: `ssl`,
`pressl`, `condo_relate` (exact, "strict"), `square_majority` (**inferred**:
majority status of the record's square+suffix), `none` (treated as not designated).

## Analysis (`data/analysis/`)

| File | Contents |
|---|---|
| `designated_shares.csv` | designated share of records / assessed value / land value, by view (`all`, `non_condo`, `strict`) × zero-tax property included/excluded |
| `designated_shares_by_ward.csv` | same, by ward (ITSPE `PRMS_WARD`) |
| `gis_summary.json` | record counts, extract dates, match-method counts, Zoning Lookup counts |
| `district_first_dates.csv` | per GIS district: first DC date and basis, expansions, era |
| `value_by_designation_era.csv` | value in districts by era of earliest covering district (`_strict`: exact matches only) |
| `inventory_summary.json` | 2009 Inventory entry counts |
| `court_mayors_agent_appeals.csv` | appeals of Mayor's Agent permit decisions: appellant (owner vs preservation/neighborhood side) × ruling × outcome for the preservation side. Appealed cases only, not approval rates |
| `dcpl_governance.json` | DCPL board: roster sizes, share of trustees with a printed architecture credential (per person across rosters), turnover between rosters, current affiliation categories, Part VI policy answers by year. No names |
| `court_appeals_summary.json` | counts, order-to-opinion lag, designation challenges, opinions not yet fetched |

## Hand-curated inputs (`inputs/`)

`district_dates.csv` — one row per dated event per GIS district (`event`:
`established_by_act`, `dc_listing`, `preliminary_listing`, `designated`,
`expanded`, `boundary_change`, `amended`, `expansion_denied`), with source
document key and PDF page. Rules: a 1964 "preliminary identification" is not a
designation; a plain DC listing is; "effective" dates are recorded separately.

`nomination_links.csv` — hand-reviewed links between records the matcher
can't pair (different names, or dates more than 120 days apart), one row per
record with the reason. A link whose record can't be found stops the build.
`joined/nominations.csv` keeps the HPRB meeting date as `outcome_date` when
there is one; `date_conflict` lists every source's date when they differ by
more than 120 days (e.g. case 11-16: HPRB 2011-08-04, FY2011 update
2010-11-18). Rows with a conflict or a missing expected source go to
`reconciliation.csv`.

`hprb_case_anchors.csv` — designation items whose HPRB action prints no
case number (Union Market Terminal, Capital Traction Company Union Station),
with the case number and the HPO document that gives it. An anchor that can't
be found in its source file stops the build.

**FY2008 count.** HPO's table reports 11 landmark designations approved in
FY2008; the reconciled data has 17, 12 of them confirmed by both an HPRB
action and the 2009 Inventory. The difference appears to be in HPO's table,
not the scrape, and is reported as is.

`dcpl_board.csv` — DCPL trustee rosters: FY2006 and FY2010–2015 from the
990s (Part VII or the attached board list), and the current board page
(2026-10). Names and credentials as listed; `affiliation_as_listed` and the
coded `affiliation_category` exist only for the current page, whose lines
are sometimes a title rather than an employer. Findings report aggregates
only. Part VI answers are in `dcpl_990_lines.csv` (FY2011–2013 checkboxes
read from page images).

`court_cases.csv` — coding of DC Court of Appeals preservation cases.
`preservation_side` is the outcome for whoever argued for preservation
(`prevailed`, `lost`, `remanded`, `mixed`); it is a coding judgment, with the
holding quoted verbatim. Private individuals are masked in `case_label`;
`cluster_id` links to the public opinion.

## Reconciliation with the exploratory figures

- **Land value share (~42%)** reproduces only on strict matches; counting
  square-majority records gives ~49%, mostly federal National Mall parcels with
  $0 assessment but ~$9B land value.
- **1964 Inventory listings:** 289 entries carry "DC listing November 8, 1964",
  matching the Inventory's own "289 listings" (exploratory: 287).
- **Value by era:** 1950, 1980s, 1990s and 2000s match within 5%. The
  five districts the exploratory pull listed as undated ($1.9B) are now dated (Meridian
  Hill 2014, Immaculata 2011, Marjorie Webster 2011, Seventeenth Street 1968,
  Grant Road 2002); the US Naval Observatory (2023, year only) also adds to
  the 2020s. 1968 DC listings (Federal Triangle, Seventeenth
  Street, National Arboretum, Washington Cathedral) are a separate "1960s
  other" bucket ($9.6B); the exploratory pull appears to have counted Federal
  Triangle ($7.0B) under Pennsylvania Avenue NHS (1973), which with it would
  give 1970s ≈ $52.4B vs $51.1B.
- **Expansions are attributed to the original designation year** (no boundary
  history yet). Ten districts have recorded expansions, including Capitol Hill
  (1976, 2002, 2015), Dupont Circle (1983, 2005), National Mall (2016),
  Financial (2016) and Anacostia (2021, ~325 properties), so later-era values
  are understated.
