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
| `mayors_agent_summary.json`, `mayors_agent_outcomes_by_decade.csv` | H6: Mayor's Agent grant rates overall, by basis (special merit, hardship, public interest, consistency) and decade; caveats |
| `court_appeals_summary.json` | counts, order-to-opinion lag, designation challenges, opinions not yet fetched |

## H2: permits and pending applications

- `data/raw/<date>/arcgis/permits_<year>/` — DOB building permits from DC GIS (`FEEDS/DCRA/FeatureServer`), one layer per issue year 2009–present, filtered to raze, demolition, new building and addition subtypes. Owner and applicant names are not fetched. Issued permits only: no application date, and no record of applications never issued.
- `data/normalized/permits.csv` — one row per permit: id, issue date, subtype, status, address, standardized address key, SSL, ward, description.
- `data/joined/nomination_permits.csv` — permits issued within 3 years of an individual-landmark nomination's reference date (first HPRB hearing, else outcome date), linked by lot (via the zoning lookup and tax roll addresses) or by address. `nomination_lot_match.csv` records which nominations resolved to an address or lot.
- `data/joined/h2_pending_applications.csv` — `inputs/h2_pending_applications.csv` with quotes checked and nominations attached.
- `data/analysis/h2_summary.json` — share of heard nominations (FY2007–2025) with a documented pending raze or alteration application, outcomes by group, and raze permits issued within 180 days after a denial or withdrawal (`h2_raze_after_denial.csv`).

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

**HPRB archive (box.com).** `normalize/hprb.py` also reads the action documents
in `data/raw/manual/hprb_box/extracted/` (HPO's meeting-records archive,
2006–2026; PDF, .docx via pandoc, legacy .doc via macOS `textutil`). An archive
action for a case within 10 days of a planning.dc.gov action is treated as the
same action and dropped; `source_file` starts with `box:` for archive rows.

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

`mayors_agent_review.csv` — dispositions read from the decision PDFs for the
64 Mayor's Agent decisions whose library description gives none; each quote is
checked against the PDF (or its OCR copy for scans) at build time.

**Mayor's Agent decisions** (`data/normalized/mayors_agent_decisions.csv`):
one row per decision in Georgetown Law Library's collection (202, 1978–2024),
collected through the user's browser into `data/raw/manual/mayors_agent/`
(`mayors_agent_catalog.json`, the decision PDFs named `<work id>__<file>`, and
`mayors_agent_download_log.json`). Disposition from the library's description
("Disposition:" field) or the review file; basis flags from the library's
subject tags, or for the 20 the library left untagged (all eight from the 2020s) the grounds the applicant claimed, read from the decision (`inputs/mayors_agent_basis_review.csv`; `basis_source` says which);
`case_type` is the primary permit sought (demolition > subdivision > new
construction > alteration; plus procedural), from the library's permit type,
tags and title or, for 26, read from the decision
(`inputs/mayors_agent_type_review.csv`; `case_type_source` says which);
`reviewing_body` / `reviewer_position` record what HPRB (the Joint
Committee on Landmarks before 1983; the Commission of Fine Arts for Georgetown)
recommended — against, favorable, mixed, no_position (referred for a
special-merit hearing) or unknown — read from every decision with a checked
quote (`inputs/mayors_agent_hprb_review.csv`); `mentions_dcpl` flags a text
mention of DCPL or Don't Tear It Down (not proof of party status);
`order_date` from the description's own date, else the catalog date
(`date_conflict` marks differences over 30 days). Court decisions from the same
collection are coded in `court_cases.csv` (`local_file`).

`court_cases.csv` — coding of DC Court of Appeals preservation cases.
`preservation_side` is the outcome for whoever argued for preservation
(`prevailed`, `lost`, `remanded`, `mixed`); it is a coding judgment, with the
holding quoted verbatim. Private individuals are masked in `case_label`;
`cluster_id` links to the public opinion.

- `h2_pending_applications.csv` — raze, alteration and new-construction applications that HPRB agendas and actions, HPO monthly notices or staff reports list alongside a pending landmark nomination (usually "(if designated)" or "[pending landmark]"). One row per case: application number, type, `order` (only where a document says which came first), source file (`box:` for the box.com archive), verbatim quote (checked by the build), note.

- `unheard_nominations.csv` — nominations an HPO monthly notice scheduled for a hearing that HPRB never acted on (withdrawn, or dropped from the agenda: outcome `not_heard`), with the notice quote (checked by the build). Found by listing every "Case YY-NN" in the HPRB agendas, actions and HPO notices (2006–2026) and checking it against `nominations.csv`; the other unmatched numbers were typos (13-03 for 13-13, 14-96 for 14-06), co-filed cases heard together (17-21 with 17-14, 21-13 with 17-09, 14-03 and 16-17 with 11-21), or folded into another case (18-17 into 19-01).

- `mayors_agent_hearing_dates.csv` — for each Mayor's Agent decision, the last hearing session before the order, with the sentence that dates it (checked by the build). `basis`: `pattern` (found by a strict pattern that skips HPRB, CFA, zoning and ANC hearings; 25 spot-checked), `hand` (read from the decision), `no_hearing` (the decision says none was held), or blank (not stated legibly). Feeds `hearing_date`, `days_hearing_to_order`, `hpa_fy` and `fy_application_to_order` in `mayors_agent_decisions.csv` and `timing*` in `mayors_agent_summary.json`.

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
