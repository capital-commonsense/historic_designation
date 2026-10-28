# Items to fetch manually

These sources block scripted access (bot challenges or 403s), so the pipeline can't fetch them. Download them in a browser and save them **unedited** under `data/raw/manual/<folder>/`. Keep the original file names where possible. Nothing in that folder is ever overwritten.

What the pipeline does with each folder today:

- `hpo_reports/`: read automatically on every build.
- `dcpl_990/`: archived, OCR'd, and the figures recorded in `inputs/dcpl_990_lines.csv`. The 990s are scanned images, so I check each OCR'd figure by eye rather than trusting it blind.
- `mayors_agent/`, `hprb_box/`: read on every build (decisions and HPRB actions, with reviewed inputs).
- `records_request/`: records released under FOIA, one dated folder per release. HPO's case log (`.doc`) is read on every build (`normalize/case_log.py`; needs macOS `textutil` or LibreOffice).
- `press/`: archived news articles cited as sources (e.g. `inputs/agreements.csv`).
- `icg_settlement/`: for the settlement text once obtained; it will be read by hand into `inputs/agreements.csv` with a checked quote.

Status as of 2026-10-18 (updated after the FY2004 990 and the City Paper article arrived). Ordered by how much each item unlocks.

## 1. DCPL Form 990 filings (H10, governance)

**Why blocked:** ProPublica returns HTTP 403 to scripted PDF downloads.
**Save to:** `data/raw/manual/dcpl_990/`. Keep ProPublica's file names.
**Already have:** FY ending 2004-03, 2005-03, 2006-03, 2010-03 (990-EZ), 2011-03 through 2015-03. Figures are in `inputs/dcpl_990_lines.csv`.

**What the new FY2004 return showed (2026-10-18):** DCPL's total revenue was $161K (Apr 2003–Mar 2004), $130K and $240K in the next two years, with no $450K receipt. So the reported Monument Realty / Potomac Place payment either came in a later year or was held outside DCPL's books. The next returns decide which.

Priority filings:

| Fiscal year end | Why | URL |
|---|---|---|
| 2007-03 | **Most needed now.** Next year that could show the Monument payment, or a restricted fund | https://projects.propublica.org/nonprofits/download-filing?path=2008_03_EO%2F52-1038849_990_200703.pdf |
| 2008-03 | Same | https://projects.propublica.org/nonprofits/download-filing?path=2009_03_EO%2F52-1038849_990_200803.pdf |
| 2009-03 (990-EZ) | Same; also the year before the ICG settlement | https://projects.propublica.org/nonprofits/download-filing?path=2009_11_EO%2F52-1038849_990EZ_200903.pdf |
| 2017-03 | Drawdown of the restricted balance built up in FY2014 (ICG era) | https://projects.propublica.org/nonprofits/download-filing?path=08_2018_prefixes_47-52%2F521038849_201703_990_2018080215560757.pdf |
| 2023-12 | Latest governance (board, Part VI) | https://projects.propublica.org/nonprofits/download-filing?path=IRS%2F521038849_202312_990_2025030723162592.pdf |

Remaining years, for complete governance and fund history:

- 2002-03 https://projects.propublica.org/nonprofits/download-filing?path=2002_11_EO%2F52-1038849_990_200203.pdf
- 2003-03 https://projects.propublica.org/nonprofits/download-filing?path=2003_11_EO%2F52-1038849_990_200303.pdf
- 2018-03 https://projects.propublica.org/nonprofits/download-filing?path=01_2020_prefixes_51-52%2F521038849_201803_990_2020010316995176.pdf
- 2019-03 https://projects.propublica.org/nonprofits/download-filing?path=04_2021_prefixes_51-52%2F521038849_201903_990_2021040617904082.pdf
- 2021-12 https://projects.propublica.org/nonprofits/download-filing?path=download990pdf_05_2023_prefixes_48-53%2F521038849_202112_990_2023051021198149.pdf
- 2022-12 https://projects.propublica.org/nonprofits/download-filing?path=download990pdf_01_2024_prefixes_47-52%2F521038849_202212_990_2024010522183786.pdf
- 2024-12 https://projects.propublica.org/nonprofits/download-filing?path=IRS%2F521038849_202412_990_2026030223953505.pdf

ProPublica lists no PDF for FY ending 2016-03 or for the 2019-20 change to calendar years (2020-12 has data but no PDF link). The IRS's Tax Exempt Organization Search or DCPL itself may have copies.

## 2. Third Church / ICG settlement agreement (H3, H10)

**Status:** terms now sourced to a contemporaneous press summary. Washington City Paper (Lydia DePillis, Dec. 20, 2010) is saved at `data/raw/manual/press/wcp_2010-12-20_dcpl_third_church_settlement.pdf`. It describes an 11-page settlement among DCPL, the Committee of 100, Third Church and ICG Properties, "received by the Court of Appeals on November 24" (2010). The agreement text itself is still missing.
**Save to:** `data/raw/manual/icg_settlement/`

The article's embedded copy is Scribd document 45707262, now behind Scribd's paywall; it isn't a route we'll use. Sources for the same document:

1. **DC Court of Appeals clerk's office:** the settlement as filed c. Nov. 24, 2010, presumably with the Committee of 100's petition for review and motion for a 60-day stay (per Scribd's public description). The case caption and number are still to be found; the clerk can search by party (Committee of 100 on the Federal City; Third Church of Christ, Scientist).
2. **The federal case:** *Third Church of Christ, Scientist v. District of Columbia Historic Preservation Review Board*, D.D.C. 1:08-cv-01371 (filed Aug. 7, 2008). RECAP searched 2026-10-19; the docket (49 entries) is saved at `data/raw/2026-10-17/court_dockets/dcd_1-08-cv-01371_third_church.json`. **The settlement is not on it.** The court stayed the case on Jan. 5, 2010 pending the DC Court of Appeals (entry 45), and the church filed a stipulation of dismissal on Apr. 15, 2014 (entry 49) attaching the Court of Appeals' order of dismissal (1 page, not in RECAP; $0.10 on PACER). The District's Aug. 14, 2009 reply (entry 40) attaches an amended lease agreement and a memorandum of understanding; those attachments are not in RECAP either. Free in RECAP: complaint (21 pp.), amended complaint (24 pp.), the District's second motion to dismiss (30 pp.), its reply (33 pp., without attachments), the April 2009 hearing transcript (52 pp.) and the stay order (5 pp.). The Court of Appeals order in entry 49 should give the case number to ask that clerk for.
3. **A DC records request:** the District was a party. See `records_request/request.md`.
4. **The parties:** DCPL, the Committee of 100, or the reporter may share a copy if asked.

## 3. Mayor's Agent decisions (H6) — done 2026-10-18

Collected through your browser: all 202 decisions in Georgetown Law's collection (catalog, 233 decision PDFs, download log) are in `data/raw/manual/mayors_agent/`. The collection's court-case files you saved under `records_request/georgetown/` are archived there too.

## 4. HPRB meeting records (H1, H3, H7)

**Done for 2006–2026:** HPO's box.com archive (the zip you provided) is extracted in `data/raw/manual/hprb_box/`, and its actions, agendas and notices are read on every build alongside the planning.dc.gov crawl. The 2008, 2011, 2012 and 2017 gap months are filled.

**Still missing:**
- **HPRB actions and agendas for 1979–2005.** The box archive starts in 2006. They would extend H1, H7 and the nomination counts back before the coverage table starts. If HPO has no electronic copies, add them to the records request.
- **Staff reports before FY2015.** H7 now rests on 122 staff reports from the crawl (FY2015–24). Earlier reports, if HPO has them, would extend the test and name more filers for FY2006–09.

## 5. Missing HPO annual reports (coverage table)

**Mostly done (2026-10-18):** the URL pattern `https://planning.dc.gov/publication/<year>-hpo-annual-report` (your find) turned up FY1989–92, 2010, 2011, 2013, 2014, 2016, 2019 and 2023. They're now in the fetch list and the snapshot. They confirm the counts already taken from the Inventory updates and add FY2001.
**Still missing:** FY1995 (no publication page), FY2024 and FY2025 (not posted yet). If FY1995 can't be found, add it to the records request.
**Not yet read:** the 1989–92 reports are short prose reports from the old Historic Preservation Division. Their designation, denial and Mayor's Agent figures are in text and lists, not the tables the parser reads, so they need reading by hand into a reviewed input.

## 6. OpenStreetMap extracts (comparison cities) — done 2026-10-18

Geofabrik state extracts for DC, New York, Pennsylvania and Massachusetts (`*-261018.osm.pbf`, about 1.2 GB, checksums verified) are in `tmp/osm/`. `make osm` reduced them to building points in `data/raw/manual/osm/`, so **`tmp/` can be deleted**; it also holds rendered video frames (`tmp/frames/`). To refresh, download newer extracts from https://download.geofabrik.de/north-america/us/ into `tmp/osm/` with their `.md5` files and rerun `make osm`.

## Not needed from you

- **Court opinions:** your CourtListener token unblocked them. All 126 are saved (`inputs/court_cases.csv` codes the preservation cases; the last three fetched, in 2026-10-19, are zoning cases with no preservation issue).
- **dccourts.gov PDFs:** the CourtListener text replaces them.
- **Zoning Commission exhibit lists:** fetched for 2000–2026 (48,872 exhibits in 823 cases). BZA cases aren't covered yet. That's a scope decision rather than a block, and it can be scripted.
- **DOB building permits:** fetched from DC's open data (2009–2026, issued permits only). Application dates and unissued applications would need a records request to DOB.
